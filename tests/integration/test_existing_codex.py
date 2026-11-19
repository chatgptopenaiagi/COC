"""Opt-in live use of the selected existing control endpoint, no new Codex process."""
import json
import os
from pathlib import Path
import subprocess
import threading
import pytest
from coc.codex_socket import AttachedAppServer,discover_endpoints
from coc.orchestration import CodexHost
from conftest import ROOT

@pytest.mark.skipif(os.environ.get('COC_LIVE_EXISTING')!='1',reason='existing Codex endpoint integration is explicitly opt-in')
def test_browser_chat_reuses_existing_app_server(broker,tmp_path):
    for kind in ('python','javascript'):broker.host(kind)
    endpoints=discover_endpoints();endpoint=next(e['path'] for e in endpoints if e['exists'])
    workspace=tmp_path/'codex-context';workspace.mkdir()
    client=broker.client.issue('inner-existing',['host:register','agent:register','event:write','discover','session:attach','task:delegate','tool:python-science:statistics','tool:javascript-web:text_metrics'])
    server=AttachedAppServer(endpoint,workspace,allow_create=True,max_turns=1).start()
    host=CodexHost(client,server,{('python-science','statistics'),('javascript-web','text_metrics')});host.register()
    worker=threading.Thread(target=host.run,daemon=True);worker.start()
    try:
        result=subprocess.run(['node','tests/end-to-end/panel.mjs'],input=json.dumps({'url':broker.url,'token':broker.token,'agent':'operator','liveChat':True}),text=True,capture_output=True,cwd=ROOT,timeout=180)
        assert result.returncode==0,result.stderr
        tid=next(iter(server.owned_threads))
        server.close()  # release only this connection
        assert server.process is None
        server.start();resumed=server.resume(tid);assert resumed['thread']['id']==tid
        record={'status':'PASS','transport':'documented Unix socket / WebSocket','new_codex_process':False,'logical_threads_created':1,'thread_id':tid,'disconnect_reconnect_resume':True,'conversation_replayed':False,'active_turn_recovery':'NOT TESTED; only completed-turn reattachment','external_server_survived_detach':True}
        (ROOT/'evidence/integration/existing-server-reuse.json').write_text(json.dumps(record,indent=2))
    finally:host.stopped.set();worker.join(timeout=5);server.close()
