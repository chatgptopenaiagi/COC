"""Read-only provenance inspection. No reference imports, executions, or writes."""
import hashlib
import json
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
reference=Path('C:/xampp/DRAGONHYDRA-CORE-NEXT-LAB/DRAGONHYDRA-SCRAPP-INTELLIGENCE')
paths=['application/living/codex_bridge.py','application/living/server.py','application/living/web/cockpit.js','tests/mission006_operator_live.py','tests/test_mission006_cockpit.py','evidence/mission-006/operator-live-20261119T080121Z/job.json','evidence/mission-006/operator-live-20261119T080121Z/results.json','evidence/mission-006/engineering-jobs/f6cf4e7457ee4155b1fbe28e7841cee8.result.json','evidence/mission-006/cockpit-unit-retest.log']
manifest=[{'path':p,'bytes':(reference/p).stat().st_size,'sha256':hashlib.sha256((reference/p).read_bytes()).hexdigest()} for p in paths]
job=json.loads((reference/paths[5]).read_text());receipt=json.loads((reference/paths[7]).read_text());log=(reference/paths[8]).read_text()
count=re.search(r'Ran (\d+) tests in ([0-9.]+)s',log)
assert count and int(count[1])==receipt['test_count']==21 and job['id']==receipt['job_id'] and log.rstrip().endswith('OK')
report={'source':'protected DRAGONHYDRA reference; read-only inspection','files':manifest,
        'request_receipt_job_identity_matches':True,'job_prefix':job['id'][:8],'thread_prefix':job['thread_id'][:8],
        'test_count_verified_from_log':int(count[1]),'unit_suite_seconds':float(count[2]),'result':'OK',
        'receipt_status':receipt['status'],'actual_process_pid':'NOT RECORDED','no_new_worker_claim':'SUPPORTED BUT INCOMPLETE',
        'new_tests_run_in_reference':False,'reference_modified_by_audit':False}
(root/'evidence/research').mkdir(exist_ok=True)
(root/'evidence/research/dragonhydra-reference.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'matched_request_and_receipt':True,'retained_unit_tests':int(count[1]),'process_reuse':'supported, no independent PID trace'}))
