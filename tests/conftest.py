import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import pytest
from coc import Client

ROOT=Path(__file__).resolve().parents[1]
PYTHON=Path(sys.executable)
NATIVE=ROOT/'kernels/rust/target/debug/coc-native.exe'
if os.name!='nt': NATIVE=ROOT/'kernels/rust/target/debug/coc-native'

def process(args, *, env=None, log=None, cwd=ROOT):
    environment=os.environ.copy()
    for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','XAI_API_KEY','COC_BOOTSTRAP_TOKEN'):environment.pop(name,None)
    environment.update(env or {})
    return subprocess.Popen([str(x) for x in args],cwd=cwd,env=environment,stdin=subprocess.DEVNULL,
        stdout=log or subprocess.DEVNULL,stderr=log or subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

def stop(p):
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)

class RunningBroker:
    def __init__(self,path):
        self.path=path;self.token=secrets.token_urlsafe(48);self.children=[];self.logs=[];self.process=None
        self.start()
    def start(self):
        ready=self.path/'ready.json'
        if ready.exists():ready.unlink()
        log=open(self.path/'broker.log','ab');self.logs.append(log)
        address=getattr(self,'url','http://127.0.0.1:0').split('://')[1]
        binary=ROOT/('dist/coc-broker.exe' if os.name=='nt' else 'dist/coc-broker')
        self.process=process([binary,'--listen',address,'--db',self.path/'broker.sqlite','--ready',ready],env={'COC_BOOTSTRAP_TOKEN':self.token},log=log)
        end=time.monotonic()+15
        while time.monotonic()<end:
            if ready.exists():
                info=json.loads(ready.read_text());self.url=info['url'];self.client=Client(self.url,self.token,'operator');return
            if self.process.poll() is not None:raise RuntimeError('broker startup failed; inspect private test log')
            time.sleep(.05)
        raise TimeoutError('broker startup timeout')
    def host(self,kind):
        principal=f'{kind}-host'
        client=self.client.issue(principal,['host:register','event:write'])
        env={'COC_URL':self.url,'COC_TOKEN':client._token,'COC_AGENT':principal}
        if kind=='python':command=[PYTHON,'-m','coc.host'];host='python-science'
        elif kind=='javascript':command=['node',ROOT/'examples/javascript-web/host.mjs'];host='javascript-web'
        elif kind=='rust':command=[NATIVE,'host'];host='rust-native'
        elif kind=='java':
            classpath=os.pathsep.join([str(ROOT/'sdk/java/build/classes'),str(ROOT/'.tools/java/*')])
            command=['java','-cp',classpath,'io.coc.EnterpriseHost'];host='java-enterprise'
            env['COC_JAVA_DB']=str(self.path/'enterprise').replace('\\','/')
        else:raise ValueError(kind)
        log=open(self.path/f'{kind}.log','ab');self.logs.append(log)
        child=process(command,env=env,log=log);self.children.append(child)
        end=time.monotonic()+20
        while time.monotonic()<end:
            found=self.client.call('COC.DISCOVER')['hosts']
            if any(h['id']==host for h in found):return child
            if child.poll() is not None:raise RuntimeError(f'{kind} host startup failed; inspect {log.name}')
            time.sleep(.1)
        raise TimeoutError(kind+' registration timeout')
    def close(self):
        for child in self.children:stop(child)
        if self.process:stop(self.process)
        for log in self.logs:log.close()

@pytest.fixture
def broker(tmp_path):
    b=RunningBroker(tmp_path)
    try:yield b
    finally:b.close()
