"""Explicit opt-in only. These tests invoke the real authenticated Codex CLI."""
import json
import os
import threading
import time
import pytest
from coc.codex import AppServer
from coc.orchestration import CodexHost
from coc.host import HostAdapter
from coc.repair import RepairLab
from conftest import ROOT

@pytest.mark.skipif(os.environ.get('COC_LIVE_CODEX')!='1',reason='live Codex is opt-in; no synthetic substitute')
def test_live_codex_application_and_repair(broker,tmp_path):
    broker.host('python')
    lab=RepairLab(tmp_path/'repair',ROOT/'examples/autonomous-repair')
    before=lab.verify();assert not before['passed']
    repair_client=broker.client.issue('repair-lab',['host:register','event:write'])
    repair_host=HostAdapter(repair_client,'repair-lab','Isolated repair laboratory',lab.tools())
    repair_host.register();repair_thread=threading.Thread(target=repair_host.run,daemon=True);repair_thread.start()
    allowed={('python-science','statistics'),*{('repair-lab',tool) for tool in lab.tools()}}
    scopes=['host:register','agent:register','event:write','discover','session:attach','task:delegate']+[f'tool:{h}:{t}' for h,t in allowed]
    client=broker.client.issue('inner-codex',scopes)
    record={'mode':'LIVE CODEX, authenticated ChatGPT CLI, real host functions','repair_before':before}
    try:
        with AppServer(tmp_path/'codex',max_turns=3) as server:
            host=CodexHost(client,server,allowed);host.register();worker=threading.Thread(target=host.run,daemon=True);worker.start()
            try:
                task=broker.client.submit('inner-codex','agent.run',{'prompt':'Use the python-science statistics tool to compute the mean of [4, 8, 12]. Call the tool; do not calculate the result yourself. Report its task receipt.','context':'science'},timeout=180,budget={'reserved_tokens':100000,'token_limit':200000})
                result=broker.client.wait(task['id'],180)
                assert result['state']=='succeeded',result.get('error')
                calls=result['result']['tool_results'];assert any(c.get('result',{}).get('mean')==8 and c['state']=='succeeded' for c in calls),result['result']
                assert all(c['parent_task_id']==task['id'] for c in calls)
                record['application_task']=result
                broker.client.call('COC.ERROR',{'kind':'application.failure','category':'application_logic','failure':before})
                task2=broker.client.submit('inner-codex','agent.run',{'prompt':'The repair-lab report average is defective. Use inspect_failure to reproduce it and inspect source. Propose a corrected return expression, apply it with apply_expression, then run verify_repair. No shell or file tools. Finish only after reporting actual test results. Do not deploy anything.','context':'repair'},timeout=180,budget={'reserved_tokens':150000,'token_limit':200000})
                result2=broker.client.wait(task2['id'],180);assert result2['state']=='succeeded',result2.get('error')
                after=lab.verify();assert after['passed']
                assert len(result2['result']['tool_results'])>=3
                tid=result['result']['thread_id'];resumed=server.resume(tid)
                assert resumed['thread']['id']==tid
                record.update(repair_task=result2,repair_after=after,thread_resume_verified=True,
                              same_app_server=result['result']['app_server_pid']==result2['result']['app_server_pid'],
                              distinct_threads=tid!=result2['result']['thread_id'],deployment_performed=False)
                assert record['same_app_server'] and record['distinct_threads']
            finally:host.stopped.set();worker.join(timeout=5)
    finally:repair_host.stopped.set();repair_thread.join(timeout=5)
    record['integrity_verified']=broker.client.call('COC.DISCOVER',{'view':'system'})['integrity_verified']
    (ROOT/'evidence/integration').mkdir(exist_ok=True)
    (ROOT/'evidence/integration/live-codex.json').write_text(json.dumps(record,indent=2))
