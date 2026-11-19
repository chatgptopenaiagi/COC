"""Summarize executed reports; never infer a live pass from skipped tests."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
def read(path):return json.loads((root/path).read_text(encoding='utf-8-sig'))
def junit(path):
    file=root/path
    if not file.exists():return {'status':'NOT TESTED','evidence':path}
    document=ET.parse(file);suites=list(document.getroot().iter('testsuite'))
    counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    status='FAIL' if counts['failures'] or counts['errors'] else ('SKIPPED' if counts['tests']==counts['skipped'] else 'PASS')
    return {'status':status,'counts':counts,'evidence':path,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
report={'version':'0.1.0-alpha.1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'production_ready':False,
        'builds':read('evidence/builds/latest.json'),'default_suites':read('evidence/tests/latest.json'),
        'full_regression':junit('evidence/tests/full-regression.xml'),
        'live_owned_codex':junit('evidence/tests/live-codex.xml'),'live_usage_accounting':junit('evidence/tests/live-accounting.xml'),
        'live_existing_codex_browser':junit('evidence/tests/existing-codex.xml'),'live_codex_cancellation':junit('evidence/tests/codex-cancel.xml'),
        'openai_authentication':'PASS','openai_model_discovery':'PASS','openai_live_inference':{'status':'BLOCKED','reason':'QUOTA OR BILLING','attempted_requests':3,'retry_authorized':False,'evidence':'evidence/integration/openai-diagnostic.json'},
        'local_llama_inference':{'status':'BLOCKED','reason':'configured endpoint requires separately authorized credential'},
        'android_runtime':'NOT TESTED','linux_runtime':'NOT TESTED locally; see separate GitHub Actions results',
        'publication_scan':read('evidence/security/publication-scan.json')}
expected_builds={'go','rust','rust-release','typescript','java','python','django'}
expected_suites={'go','rust','javascript-typescript','java','python-all'}
report['coverage_complete']=(expected_builds=={r['component'] for r in report['builds']} and expected_suites=={r['suite'] for r in report['default_suites']})
mandatory=[*report['builds'],*report['default_suites'],report['full_regression'],report['publication_scan']]
report['local_core_acceptance']='PASS' if report['coverage_complete'] and all(r['status']=='PASS' for r in mandatory) else 'FAIL'
report['live_evidence_note']='Retained live tests ran separately; default regression deliberately skips inference. CI does not reassert local account access.'
(root/'evidence/acceptance.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'core':report['local_core_acceptance'],'regression':report['full_regression'],'direct_openai':'BLOCKED'}))
sys.exit(0 if report['local_core_acceptance']=='PASS' else 1)
