"""Read-only metadata probe of THIS outer thread; never steer/start/resume it."""
import json
import os
from pathlib import Path
from coc.codex_socket import AttachedAppServer,discover_endpoints
root=Path(__file__).resolve().parents[1]
endpoints=discover_endpoints();record={'probe':'read-only metadata; no inference or new process','endpoints':endpoints}
thread=os.environ.get('CODEX_THREAD_ID')
if thread and endpoints[0]['exists']:
    try:
        with AttachedAppServer(endpoints[0]['path'],Path('C:/xampp/htdocs/CODEXINSIDECODEX')) as server:
            metadata=server.inspect_thread(thread)
            record['result']={'status':'PASS','thread_prefix':metadata['id'][:8],'state':metadata['status'],'workspace_match':True,'new_process_started':False,'conversation_read':False,'instruction_submitted':False}
    except Exception as exc:record['result']={'status':'BLOCKED','reason':type(exc).__name__,'instruction_submitted':False}
else:record['result']={'status':'UNAVAILABLE'}
# Strip machine-specific endpoint paths from published evidence.
record['endpoints']=[{k:v for k,v in e.items() if k!='path'} for e in endpoints]
(root/'evidence/integration/existing-outer-metadata.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record['result']))
