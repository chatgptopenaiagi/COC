import pytest
from coc.client import envelope,protocol_schema,Client
from coc.host import scientific_tools
import jsonschema
import threading

def test_contract_rejects_unknown_fields():
    m=envelope('test','COC.HELLO',{});jsonschema.validate(m,protocol_schema());m['unknown']=True
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(m,protocol_schema())
def test_scientific_computation():
    result=scientific_tools()['statistics'][1]({'values':[1,3,8]},threading.Event(),{})
    assert result=={'count':3,'mean':4,'sum':12}
def test_no_remote_plaintext():
    with pytest.raises(ValueError):Client('http://example.com','x','test')
