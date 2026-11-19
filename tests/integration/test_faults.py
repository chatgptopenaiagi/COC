import ctypes
import json
import os
import subprocess
import sys
import time
import psutil
import pytest
from coc import envelope,Client,COCError
from conftest import ROOT,NATIVE,stop

def test_failed_peer_becomes_uncertain_without_duplicate_execution(broker):
    host=broker.host('python')
    task=broker.client.submit('python-science','cooperative_wait',{'seconds':20})
    end=time.monotonic()+5
    while broker.client.get_task_status(task['id'])['state']!='running':
        assert time.monotonic()<end;time.sleep(.05)
    stop(host);start=time.monotonic()
    result=broker.client.wait(task['id'],16)
    elapsed=time.monotonic()-start
    assert result['state']=='outcome_unknown' and result['attempt']==1
    assert elapsed<15
    (ROOT/'evidence/recovery/peer-loss.json').write_text(json.dumps({'state':result['state'],'task_id':task['id'],'detection_seconds':elapsed,'automatic_reexecution':False},indent=2))

def test_event_replay_survives_broker_restart(broker):
    broker.client.call('COC.MESSAGE',{'kind':'checkpoint','text':'synthetic checkpoint'})
    first=list(broker.client.call('COC.DISCOVER',{'view':'system'})['events']);cursor=first[-1]['sequence']
    stop(broker.process);broker.start()
    broker.client.call('COC.MESSAGE',{'kind':'reconnected','text':'same authority'})
    stream=broker.client.events(cursor);event=next(stream);stream.close()
    assert event['sequence']>cursor and event['data']['kind']=='reconnected'
    assert broker.client.call('COC.DISCOVER',{'view':'system'})['integrity_verified']

def test_native_abi_and_owned_child_cleanup():
    library=ROOT/'kernels/rust/target/debug'/('coc_native.dll' if os.name=='nt' else 'libcoc_native.so')
    native=ctypes.CDLL(str(library));native.coc_validate_json.argtypes=[ctypes.c_void_p,ctypes.c_size_t];native.coc_validate_json.restype=ctypes.c_int
    message=json.dumps(envelope('abi','COC.HELLO',{})).encode();data=ctypes.create_string_buffer(message)
    assert native.coc_validate_json(data,len(message))==0
    completed=subprocess.run([str(NATIVE),'supervise','150',sys.executable,'-c','import time; time.sleep(10)'],capture_output=True,text=True,timeout=5)
    assert completed.returncode==0
    result=json.loads(completed.stdout);assert result['reaped'] and not result['success']
    assert not psutil.pid_exists(result['child_pid'])

def test_delegated_credential_cannot_impersonate_registered_principal(broker):
    broker.client.issue('established',['host:register'])
    issuer=broker.client.issue('limited-issuer',['auth:issue','host:register'])
    with pytest.raises(COCError):issuer.issue('established',['host:register'])

def test_cpu_and_memory_metrics_are_measured(broker):
    state=broker.client.call('COC.DISCOVER',{'view':'system'})['broker']
    actual=psutil.Process(broker.process.pid).memory_info().rss
    assert abs(state['rss_bytes']-actual)<40*1024*1024
    assert state['cpu_percent']>=0
