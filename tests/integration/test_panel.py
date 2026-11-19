import json
import os
import subprocess
from conftest import ROOT

def test_real_operator_panel(broker):
    broker.host('python')
    result=subprocess.run(['node','tests/end-to-end/panel.mjs'],input=json.dumps({'url':broker.url,'token':broker.token,'agent':'operator'}),text=True,capture_output=True,timeout=60,cwd=ROOT)
    assert result.returncode==0,result.stderr
