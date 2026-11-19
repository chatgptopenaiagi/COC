"""Explicit provider adapters and durable, fail-closed request admission.

Providers never execute model-proposed functions. Applications must validate and
route each call through COC. Unknown request outcomes retain their reservations.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

class ProviderError(RuntimeError):pass
class BudgetExceeded(ProviderError):pass

@dataclass(frozen=True)
class Policy:
    max_requests:int=3
    max_total_reserved_tokens:int=24000
    max_input_bytes:int=12000
    max_output_tokens:int=1024
    max_concurrent:int=1
    max_usd:float|None=None
    input_usd_per_million:float|None=None
    output_usd_per_million:float|None=None
    timeout_seconds:int=45

class UsageLedger:
    def __init__(self,path,policy:Policy):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.policy=policy
        if min(policy.max_requests,policy.max_concurrent,policy.max_output_tokens,policy.max_total_reserved_tokens,policy.max_input_bytes,policy.timeout_seconds)<1:raise ValueError('positive policy limits required')
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, provider TEXT, model TEXT, state TEXT, reserved_tokens INTEGER, reserved_usd REAL, usage TEXT, started REAL, finished REAL)')
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.execute('PRAGMA synchronous=FULL');return db
    def reserve(self,provider,model,input_bytes,output_tokens):
        p=self.policy
        if input_bytes>p.max_input_bytes or not 1<=output_tokens<=p.max_output_tokens:raise BudgetExceeded('per-request input/output budget exceeded')
        # UTF-8 byte count plus overhead is a conservative text-token bound, not a billing quote.
        tokens=input_bytes+512+output_tokens;usd=None
        if p.max_usd is not None:
            if p.input_usd_per_million is None or p.output_usd_per_million is None:raise BudgetExceeded('monetary budget requires configured model prices')
            usd=((input_bytes+512)*p.input_usd_per_million+output_tokens*p.output_usd_per_million)/1e6
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count,reserved,active,cost=db.execute("SELECT count(*),coalesce(sum(reserved_tokens),0),coalesce(sum(state='in_flight'),0),coalesce(sum(reserved_usd),0) FROM calls").fetchone()
            if count>=p.max_requests or reserved+tokens>p.max_total_reserved_tokens or active>=p.max_concurrent:raise BudgetExceeded('durable request/token/concurrency budget exhausted')
            if usd is not None and cost+usd>p.max_usd:raise BudgetExceeded('configured spending ceiling exceeded')
            rid=uuid.uuid4().hex;db.execute('INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?)',(rid,provider,model,'in_flight',tokens,usd,None,time.time(),None));return rid
    def finish(self,rid,state,usage=None):
        with self.connect() as db:db.execute('UPDATE calls SET state=?,usage=?,finished=? WHERE id=?',(state,json.dumps(usage),time.time(),rid))
    def records(self):
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY started')]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ProviderError('provider redirects are prohibited')

def valid_url(url,local=False):
    p=urllib.parse.urlparse(url)
    if p.username or p.password or p.query or p.fragment or not p.hostname:raise ValueError('invalid provider URL')
    if p.scheme!='https' and not (local and p.scheme=='http' and p.hostname in ('127.0.0.1','localhost','::1')):raise ValueError('HTTPS required outside loopback')

class HTTPProvider:
    def __init__(self,name,url,model,ledger,*,key_file=None,local=False,wire='responses',context_limit=None,tool_calling=True):
        valid_url(url,local)
        if name=='openai' and urllib.parse.urlparse(url).hostname!='api.openai.com':raise ValueError('OpenAI credentials require the official OpenAI API origin')
        self.name=name;self.url=url.rstrip('/');self.model=model;self.ledger=ledger;self.key_file=Path(key_file) if key_file else None
        self.local=local;self.wire=wire;self.context_limit=context_limit;self.tool_calling=tool_calling
    def capabilities(self):
        return {'provider':self.name,'model':self.model,'wire':self.wire,'context_limit':self.context_limit,
                'tool_calling':self.tool_calling,'authentication':'key file' if self.key_file else ('none configured' if self.local else 'required'),
                'cancellation':'before-send only; an in-flight HTTP inference may continue remotely until provider timeout',
                'usage':'provider-reported when returned','unsupported':['background jobs','vision','audio'],'local':self.local}
    def _headers(self):
        headers={'Content-Type':'application/json'}
        if self.key_file:
            if self.key_file.is_symlink():raise ProviderError('credential symlinks are not accepted')
            key=self.key_file.read_text(encoding='utf-8-sig').strip()
            if not key or '\n' in key or len(key)>4096:raise ProviderError('credential file is invalid')
            headers['x-api-key' if self.wire=='anthropic' else 'Authorization']=key if self.wire=='anthropic' else 'Bearer '+key
        elif not self.local:raise ProviderError('provider requires an explicitly configured credential file')
        if self.wire=='anthropic':headers['anthropic-version']='2023-06-01'
        return headers
    def generate(self,prompt,*,tools=None,max_output_tokens=256,cancelled=None):
        if cancelled and cancelled.is_set():raise InterruptedError()
        tools=tools or []
        if tools and not self.tool_calling:raise ProviderError('tool calling is not enabled for this configured model')
        p=self.ledger.policy
        if self.wire=='responses':
            body={'model':self.model,'input':prompt,'max_output_tokens':max_output_tokens,'store':False}
            if tools:body['tools']=[{'type':'function','name':t['name'],'description':t['description'],'parameters':t['input_schema']} for t in tools]
            endpoint='/responses'
        elif self.wire=='anthropic':
            body={'model':self.model,'messages':[{'role':'user','content':prompt}],'max_tokens':max_output_tokens}
            if tools:body['tools']=[{'name':t['name'],'description':t['description'],'input_schema':t['input_schema']} for t in tools]
            endpoint='/messages'
        elif self.wire=='chat':
            body={'model':self.model,'messages':[{'role':'user','content':prompt}],'max_tokens':max_output_tokens,'stream':False}
            if tools:body['tools']=[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['input_schema']}} for t in tools]
            endpoint='/chat/completions'
        else:raise ProviderError('unsupported wire protocol')
        encoded=json.dumps(body).encode();headers=self._headers()
        rid=self.ledger.reserve(self.name,self.model,len(encoded),max_output_tokens)
        request=urllib.request.Request(self.url+endpoint,encoded,headers)
        start=time.monotonic()
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=p.timeout_seconds) as response:
                raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:raise ProviderError('provider response too large')
                data=json.loads(raw)
        except urllib.error.HTTPError as exc:
            classification='unclassified'
            try:
                detail=json.loads(exc.read(65536)).get('error',{})
                code=detail.get('code') or detail.get('type')
                if code in ('insufficient_quota','rate_limit_exceeded','invalid_api_key','model_not_found','billing_hard_limit_reached'):classification=code
                elif any(word in str(detail.get('message','')).lower() for word in ('quota','billing','credit','balance')):classification='quota_or_billing'
                elif 'rate' in str(detail.get('message','')).lower():classification='rate_limit'
            except (ValueError,AttributeError):classification='non_json_or_unrecognized_error'
            self.ledger.finish(rid,'http_error',{'http_status':exc.code,'classification':classification})
            # Never include response bodies, which might echo credentials or sensitive requests.
            raise ProviderError(f'{self.name} returned HTTP {exc.code} ({classification}); no automatic retry') from None
        except Exception:
            self.ledger.finish(rid,'outcome_unknown')
            raise ProviderError(f'{self.name} request interrupted or invalid; consumption may have occurred') from None
        finally:headers.clear();request.remove_header('Authorization');request.remove_header('X-api-key')
        usage=data.get('usage');self.ledger.finish(rid,'completed',usage)
        text=[];calls=[]
        if self.wire=='responses':
            for item in data.get('output',[]):
                if item.get('type')=='message':text.extend(c.get('text','') for c in item.get('content',[]) if c.get('type')=='output_text')
                if item.get('type')=='function_call':calls.append({'id':item.get('call_id'),'name':item['name'],'arguments':json.loads(item['arguments'])})
        elif self.wire=='anthropic':
            for item in data.get('content',[]):
                if item.get('type')=='text':text.append(item['text'])
                if item.get('type')=='tool_use':calls.append({'id':item['id'],'name':item['name'],'arguments':item['input']})
        else:
            message=data['choices'][0]['message'];text.append(message.get('content') or '')
            calls=[{'id':c['id'],'name':c['function']['name'],'arguments':json.loads(c['function']['arguments'])} for c in message.get('tool_calls',[])]
        return {'provider':self.name,'model':data.get('model',self.model),'provider_response_id':data.get('id'),'ledger_id':rid,
                'text':'\n'.join(text),'tool_calls':calls,'usage':usage,'elapsed_seconds':time.monotonic()-start,'status':data.get('status','completed')}
    def discover_models(self):
        request=urllib.request.Request(self.url+'/models',headers=self._headers())
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=5) as response:return json.load(response)
        except urllib.error.HTTPError as exc:raise ProviderError(f'{self.name} model discovery HTTP {exc.code}') from None

def configured_provider(config,ledger):
    name=config['provider'];common={'model':config['model'],'ledger':ledger,'key_file':config.get('key_file'),'context_limit':config.get('context_limit')}
    if name=='openai':return HTTPProvider(name,'https://api.openai.com/v1',**common,wire='responses')
    if name=='anthropic':return HTTPProvider(name,'https://api.anthropic.com/v1',**common,wire='anthropic')
    if name=='xai':return HTTPProvider(name,'https://api.x.ai/v1',**common,wire='responses')
    if name=='microsoft':
        url=config['url'];host=urllib.parse.urlparse(url).hostname or ''
        if not host.endswith(('.openai.azure.com','.services.ai.azure.com')):raise ValueError('explicit Microsoft Azure endpoint required')
        return HTTPProvider(name,url,**common,wire='responses')
    if name in ('llama.cpp','ollama','local-openai'):
        return HTTPProvider(name,config['url'],**common,local=True,wire='chat',tool_calling=config.get('tool_calling',False))
    raise ProviderError(f'{name}: no verified adapter; unsupported rather than simulated')
