"""Verify bytes, install the wheel offline and run the unpacked four-host engine."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
root=Path(__file__).resolve().parents[1];record=json.loads((root/'evidence/releases/latest.json').read_text());archive=root/record['archive']
assert hashlib.sha256(archive.read_bytes()).hexdigest()==record['sha256']
destination=root/'.runtime'/('package-verification-'+str(time.time_ns()));destination.mkdir()
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        target=(destination/name).resolve()
        if not target.is_relative_to(destination.resolve()):raise ValueError('unsafe archive path')
    z.extractall(destination)
package=next(destination.iterdir());manifest=json.loads((package/'RELEASE-MANIFEST.json').read_text())
for item in manifest['files']:assert hashlib.sha256((package/item['path']).read_bytes()).hexdigest()==item['sha256']
subprocess.run([sys.executable,'-m','venv',str(package/'.venv')],check=True,capture_output=True)
python=package/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
wheel=next((package/'dist/python').glob('*.whl'))
subprocess.run([str(python),'-m','pip','install','--no-index','--find-links',str(package/'dist/wheelhouse'),str(wheel)],check=True,capture_output=True)
env=os.environ.copy();env.pop('PYTHONPATH',None)
def control(command,*extra):
    completed=subprocess.run([str(python),'-m','coc.control',command,'--root',str(package),*extra],cwd=package,env=env,capture_output=True,text=True,timeout=60)
    if completed.returncode:raise RuntimeError('packaged controller failed: '+completed.stderr[-1000:])
    return json.loads(completed.stdout)
try:
    started=control('start','--demo','--port','0')
    from coc.secrets import SecretStore
    from coc import Client
    client=Client(started['url'],SecretStore(package/'.runtime/installation/private').get_or_create('bootstrap'),'operator')
    deadline=time.monotonic()+30
    while len(client.discover_capabilities()['hosts'])<4:
        if time.monotonic()>deadline:raise RuntimeError('packaged hosts did not register')
        time.sleep(.2)
    cases=[('python-science','statistics',{'values':[2,4]},'mean',3),('java-enterprise','invoice',{'units':2,'unit_price':'3.50'},'total','7.00'),('javascript-web','text_metrics',{'text':'packaged host'},'words',2),('rust-native','sum',{'values':[5,6]},'sum',11)]
    results=[]
    for host,tool,args,key,expected in cases:
        task=client.wait(client.submit(host,tool,args)['id'],15)
        assert task['state']=='succeeded' and task['result'][key]==expected
        results.append({'host':host,'task_id':task['id'],'result':task['result'],'receipt_id':task['receipt']['id']})
    assert client.call('COC.DISCOVER',{'view':'system'})['integrity_verified']
    record['independent_execution']='PASS';record['verified_tasks']=results;record['wheel_installed_offline']=True;record['manifest_hashes_verified']=len(manifest['files'])
finally:control('stop')
(root/'evidence/releases/latest.json').write_text(json.dumps(record,indent=2));print(json.dumps({'independent_package':'PASS','hosts':len(results),'sha256':record['sha256']}))
