import copy
import json
import os
import subprocess
from coc.client import envelope,protocol_schema
import jsonschema
from conftest import ROOT,NATIVE

def test_shared_envelope_corpus():
    good=envelope('conformance','COC.HELLO',{})
    corpus=[good]
    for key in good['params']:
        invalid=copy.deepcopy(good);del invalid['params'][key];corpus.append(invalid)
    for path,value in [('method','COC.UNKNOWN'),('jsonrpc','1.0'),('id',17)]:
        invalid=copy.deepcopy(good);invalid[path]=value;corpus.append(invalid)
    invalid=copy.deepcopy(good);invalid['params']['timestamp']='yesterday';corpus.append(invalid)
    invalid=copy.deepcopy(good);invalid['extra']=True;corpus.append(invalid)
    payload=''.join(json.dumps(item)+'\n' for item in corpus)
    validator=jsonschema.Draft7Validator(protocol_schema(),format_checker=jsonschema.FormatChecker())
    expected=[validator.is_valid(item) for item in corpus]
    assert expected==[True]+[False]*(len(corpus)-1)
    classpath=os.pathsep.join([str(ROOT/'sdk/java/build/classes'),str(ROOT/'.tools/java/*')])
    programs={'rust':[str(NATIVE),'validate'],'typescript':['node','tests/protocol/validate-node.mjs'],'java':['java','-cp',classpath,'io.coc.EnterpriseHost','validate','specifications/schemas/message.schema.json']}
    for name,command in programs.items():
        result=subprocess.run(command,input=payload,text=True,capture_output=True,cwd=ROOT,timeout=30)
        assert result.returncode==0,(name,result.stderr)
        assert [json.loads(line)['valid'] for line in result.stdout.splitlines()]==expected,name
    (ROOT/'evidence/tests').mkdir(exist_ok=True)
    (ROOT/'evidence/tests/conformance.json').write_text(json.dumps({'cases':len(corpus),'implementations':['python',*programs],'passed':True},indent=2))
