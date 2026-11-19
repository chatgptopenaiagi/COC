"""Application-aware Codex host. Dynamic calls become durable child tasks."""
import argparse
import json
from pathlib import Path
import signal
import time
from .client import Client
from .codex import AppServer
from .host import HostAdapter,capability

class CodexHost(HostAdapter):
    def __init__(self,client,server,allowed):
        self.server=server;self.allowed=allowed;self.threads={}
        descriptor=capability('agent.run','Run a bounded application-aware Codex turn',
            {'type':'object','properties':{'prompt':{'type':'string','maxLength':16000},'context':{'type':'string','maxLength':128}},'required':['prompt'],'additionalProperties':False},
            {'type':'object','required':['thread_id','turn_id','tool_results','status']},idempotent=False)
        super().__init__(client,'inner-codex','Application-aware Codex',{'agent.run':(descriptor,self.reason)})
    def register(self):
        self.client.call('COC.REGISTER',{'kind':'agent','id':self.client.agent,'name':'Inner Codex','provider':'codex-app-server','process_id':self.server.process_id(),'capabilities':['dynamic-tools','thread/start','thread/resume','turn/interrupt'],'experimental':['dynamic-tools']})
        return super().register()
    def reason(self,args,cancelled,parent):
        if parent['budget']['reserved_tokens']<1024:raise ValueError('Codex tasks require an explicit token reservation (including provider context overhead)')
        hosts=self.client.call('COC.DISCOVER')['hosts'];mapping={};specs=[]
        for host in hosts:
            for cap in host['capabilities']:
                pair=(host['id'],cap['name'])
                if pair not in self.allowed:continue
                name='coc_'+str(len(mapping)+1);mapping[name]=pair
                specs.append({'type':'function','name':name,'description':host['id']+'.'+cap['name']+': '+cap['description'],'inputSchema':cap['input_schema']})
        context=args.get('context') or parent['id']
        if context not in self.threads:
            thread=self.server.create_thread(specs)
            self.threads[context]=(thread['thread']['id'],mapping)
            self.client.call('COC.ATTACH',{'session_id':thread['thread']['id'],'codex_thread_id':thread['thread']['id'],'host_id':self.id})
        tid,mapping=self.threads[context]
        def execute(name,arguments,call_id):
            if name not in mapping:raise PermissionError('tool not exposed')
            host,tool=mapping[name]
            if isinstance(arguments,str):arguments=json.loads(arguments)
            child=self.client.submit(host,tool,arguments,parent_id=parent['id'],key=tid+':'+call_id,timeout=60)
            end=time.monotonic()+60
            while time.monotonic()<end:
                if cancelled.is_set():
                    self.client.cancel_task(child['id']);raise InterruptedError()
                result=self.client.get_task_status(child['id'])
                if result['state'] in ('succeeded','failed','cancelled','outcome_unknown'):
                    return {'task_id':child['id'],'parent_task_id':parent['id'],'state':result['state'],'result':result.get('result'),'receipt':result.get('receipt'),'error':result.get('error')}
                time.sleep(.1)
            raise TimeoutError('host operation still pending; do not retry blindly')
        result=self.server.run(tid,args['prompt'],execute,cancelled,max_tokens=parent['budget']['reserved_tokens'],timeout=min(150,max(1,(parent['deadline']-time.time()*1000)/1000-2)))
        self.client.call('COC.EVENT',{'task_id':parent['id'],'kind':'codex.turn.completed','thread_id':tid,'turn_id':result['turn_id'],'usage':result['usage']})
        return result
    def usage_tokens(self,result):return result.get('usage_tokens',0)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cwd',default='.runtime/inner-workspace');parser.add_argument('--allow',action='append',default=[]);parser.add_argument('--max-turns',type=int,default=3)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--socket');mode.add_argument('--owned',action='store_true');args=parser.parse_args()
    allowed={tuple(value.split(':',1)) for value in args.allow}
    if not allowed:raise SystemExit('At least one explicit host:tool allow rule is required')
    from .codex_socket import AttachedAppServer,discover_endpoints
    context=Path(args.cwd).resolve();context.mkdir(parents=True,exist_ok=True)
    if args.owned:connection=AppServer(context,max_turns=args.max_turns)
    else:
        endpoint=args.socket or next((e['path'] for e in discover_endpoints() if e['exists']),None)
        if not endpoint:raise SystemExit('No authorized control endpoint found. Select --socket or explicitly allow --owned; no automatic duplicate process.')
        connection=AttachedAppServer(endpoint,context,allow_create=True,max_turns=args.max_turns)
    with connection as server:
        host=CodexHost(Client.from_env(),server,allowed);signal.signal(signal.SIGINT,lambda *_:host.stopped.set());host.run()
if __name__=='__main__':main()
