"""Allowlisted prerelease package with native binaries, wheel, JAR, UI and source."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
root=Path(__file__).resolve().parents[1]
acceptance=json.loads((root/'evidence/acceptance.json').read_text())
if acceptance['local_core_acceptance']!='PASS':raise SystemExit('full local core acceptance must pass before packaging')
version='0.1.0-alpha.2';stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
platform='windows-x64' if os.name=='nt' else 'linux-x64'
directory=root/'dist/packages'/f'COC-{version}-{platform}-{stamp}'
directory.mkdir(parents=True,exist_ok=False)
def copy(source,target):
    destination=directory/target;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root)
for raw in files.split(b'\0'):
    if not raw:continue
    path=raw.decode()
    if path.startswith(('.github/','evidence/releases/')) or path=='scripts/audit-reference.py':continue
    copy(root/path,path)
binary='coc-broker.exe' if os.name=='nt' else 'coc-broker';native='coc-native.exe' if os.name=='nt' else 'coc-native';library='coc_native.dll' if os.name=='nt' else 'libcoc_native.so'
copy(root/'dist'/binary,'dist/'+binary)
for name in (native,library):copy(root/'kernels/rust/target/release'/name,'dist/'+name)
copy(root/'sdk/java/build/coc-java-sdk.jar','sdk/java/build/coc-java-sdk.jar')
for jar in (root/'.tools/java').glob('*.jar'):copy(jar,'sdk/java/dependencies/'+jar.name)
wheel=max((root/'dist/python').glob('*.whl'),key=lambda p:p.stat().st_mtime);copy(wheel,'dist/python/'+wheel.name)
if not (root/'dist/wheelhouse').is_dir():raise SystemExit('offline wheelhouse must be populated before packaging')
for dependency in (root/'dist/wheelhouse').glob('*.whl'):copy(dependency,'dist/wheelhouse/'+dependency.name)
dependency=root/'node_modules/@cfworker/json-schema'
shutil.copytree(dependency,directory/'node_modules/@cfworker/json-schema')
# Preserve distributable third-party notices from actual resolved dependency trees.
notice_roots=[root/'.tools/cargo/registry/src']
go_cache=subprocess.check_output(['go','env','GOMODCACHE'],text=True).strip()
notice_roots.append(Path(go_cache))
notices=directory/'THIRD_PARTY_LICENSES';notices.mkdir()
for base in notice_roots:
    if not base.is_dir():continue
    for pattern in ('LICENSE','LICENSE-MIT','LICENSE-APACHE','COPYING','NOTICE'):
        for path in base.rglob(pattern):
            if path.is_file() and path.stat().st_size<200000:
                label=hashlib.sha256(str(path.parent).encode()).hexdigest()[:12]+'-'+path.parent.name+'-'+path.name
                shutil.copyfile(path,notices/label)
subprocess.run([sys.executable,str(root/'scripts/scan-secrets.py'),'--directory',str(directory)],cwd=root,check=True)
manifest={'project':'COC','version':version,'platform':platform,'built_at':stamp,'status':'engineering prerelease','production_ready':False,
          'native_profile':'release','api_inference':'BLOCKED: quota/billing','files':[]}
for path in sorted(directory.rglob('*')):
    if path.is_file():manifest['files'].append({'path':path.relative_to(directory).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(directory/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
archive=directory.parent/(directory.name+'.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in directory.rglob('*'):
        if path.is_file():z.write(path,directory.name+'/'+path.relative_to(directory).as_posix())
sha=hashlib.sha256(archive.read_bytes()).hexdigest();archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n')
record={'version':version,'archive':str(archive.relative_to(root)).replace('\\','/'),'sha256':sha,'bytes':archive.stat().st_size,'files':len(manifest['files']),'package_directory':str(directory.relative_to(root)).replace('\\','/'),'independent_execution':'PENDING'}
(root/'evidence/releases').mkdir(exist_ok=True);(root/'evidence/releases/latest.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
