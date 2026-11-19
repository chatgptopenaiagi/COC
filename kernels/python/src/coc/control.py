"""User-session lifecycle controller. Owns only recorded COC processes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import webbrowser
import psutil
from .client import Client
from .secrets import SecretStore,protect_directory

class Controller:
    def __init__(self,root,data=None):
        self.root=Path(root).resolve();self.data=Path(data or self.root/'.runtime/installation').resolve()
        self.statefile=self.data/'processes.json';self.ready=self.data/'ready.json'
    def state(self):return json.loads(self.statefile.read_text()) if self.statefile.exists() else {'processes':[]}
    def owned(self,entry):
        try:
            p=psutil.Process(entry['pid'])
            return p if abs(p.create_time()-entry['created'])<.01 and str(Path(p.exe()).resolve()).lower()==entry['executable'].lower() else None
        except psutil.Error:return None
    def client(self):
        info=json.loads(self.ready.read_text());secret=SecretStore(self.data/'private').get_or_create('bootstrap')
        return Client(info['url'],secret,'operator')
    def spawn(self,args,env,label):
        child_env=os.environ.copy()
        for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','XAI_API_KEY','COC_TOKEN','COC_BOOTSTRAP_TOKEN'):child_env.pop(key,None)
        child_env.update(env)
        with (self.data/(label+'.log')).open('ab') as log:
            p=subprocess.Popen([str(a) for a in args],cwd=self.root,env=child_env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS) if os.name=='nt' else 0,start_new_session=os.name!='nt')
        info=psutil.Process(p.pid);entry={'pid':p.pid,'created':info.create_time(),'executable':str(Path(info.exe()).resolve()),'component':label}
        state=self.state();state['processes'].append(entry)
        self.statefile.write_text(json.dumps(state,indent=2));return entry
    def start(self,demo=False,codex=False,port=7310):
        protect_directory(self.data)
        if any(self.owned(e) for e in self.state()['processes']):raise RuntimeError('recorded COC processes are already running; inspect status or stop first')
        self.statefile.write_text(json.dumps({'processes':[]}))
        if self.ready.exists():self.ready.unlink()
        secret=SecretStore(self.data/'private').get_or_create('bootstrap')
        binary=self.root/'dist'/('coc-broker.exe' if os.name=='nt' else 'coc-broker')
        self.spawn([binary,'--listen',f'127.0.0.1:{port}','--db',self.data/'broker.sqlite3','--ready',self.ready],{'COC_BOOTSTRAP_TOKEN':secret},'broker')
        deadline=time.monotonic()+15
        while not self.ready.exists():
            if time.monotonic()>deadline:raise TimeoutError('broker startup failed; inspect private broker.log')
            time.sleep(.1)
        client=self.client();client.call('COC.HELLO')
        if demo:
            native=self.root/'kernels/rust/target/debug'/('coc-native.exe' if os.name=='nt' else 'coc-native')
            packaged=self.root/'dist'/native.name
            if packaged.exists():native=packaged
            deps=self.root/'.tools/java'
            if not deps.is_dir():deps=self.root/'sdk/java/dependencies'
            classpath=os.pathsep.join([str(self.root/'sdk/java/build/coc-java-sdk.jar'),str(deps/'*')])
            commands={'python':[sys.executable,'-m','coc.host'],'javascript':['node',self.root/'examples/javascript-web/host.mjs'],'java':['java','-cp',classpath,'io.coc.EnterpriseHost'],'rust':[native,'host']}
            for name,command in commands.items():
                principal='host-'+name;grant=client.issue(principal,['host:register','event:write'],ttl=86400)
                self.spawn(command,{'COC_URL':client.url,'COC_AGENT':principal,'COC_TOKEN':grant._token,'COC_JAVA_DB':str(self.data/'enterprise')},name)
        if codex:
            principal='inner-codex';grant=client.issue(principal,['host:register','agent:register','event:write','discover','session:attach','task:delegate','tool:python-science:statistics','tool:javascript-web:text_metrics'],ttl=86400)
            self.spawn([sys.executable,'-m','coc.orchestration','--cwd',self.data/'agent-context','--allow','python-science:statistics','--allow','javascript-web:text_metrics'],{'COC_URL':client.url,'COC_AGENT':principal,'COC_TOKEN':grant._token},'codex-connector')
        return {'status':'STARTED','url':client.url,'mode':'user-session','demo_hosts_requested':demo,'codex_connector_requested':codex}
    def stop(self):
        state=self.state()
        try:self.client().call('COC.SHUTDOWN')
        except (OSError,RuntimeError,KeyError):pass
        deadline=time.monotonic()+6
        while any(e['component']=='broker' and self.owned(e) for e in state['processes']) and time.monotonic()<deadline:time.sleep(.1)
        for entry in reversed(state['processes']):
            process=self.owned(entry)
            if not process:continue
            try:children=process.children(recursive=True)
            except psutil.NoSuchProcess:continue
            for p in reversed(children+[process]):
                try:p.terminate()
                except psutil.Error:pass
            _,alive=psutil.wait_procs(children+[process],timeout=3)
            for p in alive:
                try:p.kill()
                except psutil.Error:pass
        return {'status':'STOPPED','preserved_database':True}
    def status(self):
        processes=[{**e,'running':self.owned(e) is not None} for e in self.state()['processes']]
        try:snapshot=self.client().call('COC.DISCOVER',{'view':'system'});return {'status':'RUNNING','url':self.client().url,'processes':processes,'snapshot':snapshot}
        except (OSError,RuntimeError,KeyError):return {'status':'STOPPED_OR_UNAVAILABLE','processes':processes}
    def open_panel(self):
        client=self.client();ticket=client.call('COC.AUTHENTICATE',{'action':'panel_ticket'})
        webbrowser.open(client.url+'/#ticket='+ticket['ticket'])
        return {'status':'BROWSER_REQUESTED','url':client.url,'credential':'one-use code; no provider key'}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','stop','status','recover','open','doctor']);p.add_argument('--root',default='.');p.add_argument('--data');p.add_argument('--demo',action='store_true');p.add_argument('--codex',action='store_true');p.add_argument('--port',type=int,default=7310);args=p.parse_args();c=Controller(args.root,args.data)
    if args.command=='start':result=c.start(args.demo,args.codex,args.port)
    elif args.command=='stop':result=c.stop()
    elif args.command=='status':result=c.status()
    elif args.command=='open':result=c.open_panel()
    elif args.command=='recover':
        result=c.client().call('COC.RECOVER');result={'uncertain_tasks':[t for t in result['tasks'] if t['state']=='outcome_unknown'],'automatic_retry':False}
    else:
        from .codex_socket import discover_endpoints
        result={'tools':{name:shutil.which(name) is not None for name in ('go','cargo','java','javac','node','npm','git','codex')},'python':sys.version.split()[0],'api_key_file_present':(c.root/'openai-api-key.txt').is_file(),'codex_endpoints':discover_endpoints(),'runtime':c.status()['status']}
        result['tools']['cargo']=result['tools']['cargo'] or (c.root/'.tools/cargo/bin/cargo.exe').is_file()
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
