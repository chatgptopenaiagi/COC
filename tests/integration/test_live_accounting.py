import json
import os
import threading
import pytest
from coc.codex import AppServer
from coc.orchestration import CodexHost
from conftest import ROOT

@pytest.mark.skipif(os.environ.get('COC_LIVE_CODEX_ACCOUNTING')!='1',reason='separate bounded live accounting verification')
def test_live_codex_usage_reaches_task_ledger(broker,tmp_path):
    broker.host('python')
    client=broker.client.issue('inner-accounting',['host:register','agent:register','event:write','discover','session:attach','task:delegate','tool:python-science:statistics'])
    with AppServer(tmp_path/'context',max_turns=1) as server:
        host=CodexHost(client,server,{('python-science','statistics')});host.register()
        worker=threading.Thread(target=host.run,daemon=True);worker.start()
        try:
            task=broker.client.submit('inner-codex','agent.run',{'prompt':'Call the python-science statistics tool exactly once with values [6, 10]. Then report its returned mean briefly.'},budget={'reserved_tokens':100000,'token_limit':100000},timeout=120)
            result=broker.client.wait(task['id'],130)
            assert result['state']=='succeeded',result.get('error')
            assert 0<result['budget']['used_tokens']<=100000
            assert result['result']['tool_results'][0]['result']['mean']==8
            assert result['budget']['used_tokens']==result['result']['usage_tokens']
            (ROOT/'evidence/integration/live-codex-accounting.json').write_text(json.dumps(result,indent=2))
        finally:host.stopped.set();worker.join(timeout=5)
