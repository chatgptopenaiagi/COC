import json
import os
import threading
import time
import pytest
from coc.codex_socket import AttachedAppServer,discover_endpoints
from coc.orchestration import CodexHost
from conftest import ROOT

@pytest.mark.skipif(os.environ.get('COC_LIVE_CODEX_CANCEL')!='1',reason='explicit live Codex cancellation test')
def test_real_codex_cancellation_through_host_task(broker,tmp_path):
    broker.host('python');workspace=tmp_path/'context';workspace.mkdir()
    endpoint=next(e['path'] for e in discover_endpoints() if e['exists'])
    client=broker.client.issue('inner-cancel',['host:register','agent:register','event:write','discover','session:attach','task:delegate','tool:python-science:cooperative_wait'])
    with AttachedAppServer(endpoint,workspace,allow_create=True,max_turns=1) as server:
        host=CodexHost(client,server,{('python-science','cooperative_wait')});host.register()
        worker=threading.Thread(target=host.run,daemon=True);worker.start()
        try:
            task=broker.client.submit('inner-codex','agent.run',{'prompt':'Execute the cooperative_wait application tool with seconds 20. Wait for its actual receipt.'},timeout=90,budget={'reserved_tokens':100000,'token_limit':100000})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                children=[t for t in broker.client.call('COC.DISCOVER',{'view':'system'})['tasks'] if t.get('parent_id')==task['id'] and t['state']=='running']
                if children:break
                time.sleep(.1)
            assert children,'the real model did not invoke the host tool'
            start=time.monotonic();broker.client.cancel_task(task['id']);ack=time.monotonic()-start
            parent=broker.client.wait(task['id'],12);child=broker.client.wait(children[0]['id'],5)
            assert parent['state']=='cancelled' and child['state']=='cancelled'
            tid=next(iter(server.owned_threads))
            turns=server.request('thread/turns/list',{'threadId':tid,'limit':1,'itemsView':'notLoaded','sortDirection':'desc'})
            assert turns['data'][0]['status']=='interrupted'
            (ROOT/'evidence/integration/live-codex-cancel.json').write_text(json.dumps({'status':'PASS','parent_task_id':task['id'],'child_task_id':child['id'],'thread_id':tid,'codex_turn_status':'interrupted','parent_state':parent['state'],'child_state':child['state'],'ack_seconds':ack,'end_to_end_cancel_seconds':time.monotonic()-start,'remote_billing_guarantee':False},indent=2))
        finally:host.stopped.set();worker.join(timeout=5)
