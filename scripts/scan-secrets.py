"""Fail closed before commit/package; emits filenames and counts, never matches."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--directory');args=parser.parse_args()
keyfile=root/'openai-api-key.txt'
authorized_key=keyfile.read_bytes().strip() if keyfile.is_file() else b''
forbidden=('openai-api-key.txt','.env','.env.local','.env.production','auth.json','bridge.key')
patterns=[re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{28,}'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
if args.directory:
    base=Path(args.directory).resolve();files=[p for p in base.rglob('*') if p.is_file()]
else:
    base=root
    output=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root)
    files=[root/p.decode() for p in output.split(b'\0') if p]
    ignored=subprocess.run(['git','check-ignore','--quiet','openai-api-key.txt'],cwd=root).returncode==0
    if not ignored:raise SystemExit('credential filename is not excluded by Git')
failures=[]
for path in files:
    relative=path.relative_to(base).as_posix()
    if path.is_symlink():failures.append({'file':relative,'reason':'symlink requires manual review'});continue
    if path.name.lower() in forbidden or any(part in ('.runtime','.tools','.venv','.git') for part in path.relative_to(base).parts):
        failures.append({'file':relative,'reason':'private file in publication set'});continue
    data=path.read_bytes()
    if (len(authorized_key)>20 and authorized_key in data) or any(pattern.search(data) for pattern in patterns):failures.append({'file':relative,'reason':'credential-shaped content'})
report={'status':'FAIL' if failures else 'PASS','files_scanned':len(files),'failures':failures,'actual_key_compared_in_memory':bool(authorized_key),'key_value_logged':False}
if not args.directory:
    (root/'evidence/security').mkdir(exist_ok=True)
    (root/'evidence/security/publication-scan.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report));sys.exit(1 if failures else 0)
