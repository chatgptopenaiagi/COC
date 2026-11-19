"""One small direct API request; ledger persists across test runs."""
import json
import os
import pytest
from coc.providers import Policy,UsageLedger,configured_provider
from conftest import ROOT

@pytest.mark.skipif(os.environ.get('COC_LIVE_OPENAI')!='1',reason='billable OpenAI tests require explicit opt-in')
def test_live_openai_tool_delegation(broker):
    broker.host('python')
    ledger=UsageLedger(ROOT/'.runtime/openai-integration-budget.sqlite',Policy())
    provider=configured_provider({'provider':'openai','model':'gpt-4.1-mini','key_file':str(ROOT/'openai-api-key.txt'),'context_limit':1047576},ledger)
    # No patient, application secrets, or filesystem context is sent to the model.
    tool={'name':'statistics','description':'Compute the mean of supplied numbers in the authorized scientific host',
          'input_schema':{'type':'object','properties':{'values':{'type':'array','items':{'type':'number'}}},'required':['values'],'additionalProperties':False}}
    result=provider.generate('Call statistics exactly once with values [3, 6, 9]. Do not calculate it yourself.',tools=[tool],max_output_tokens=128)
    assert len(result['tool_calls'])==1
    call=result['tool_calls'][0];assert call['name']=='statistics' and call['arguments']=={'values':[3,6,9]}
    task=broker.client.submit('python-science',call['name'],call['arguments'],key=result['ledger_id'])
    finished=broker.client.wait(task['id'],10);assert finished['state']=='succeeded' and finished['result']['mean']==6
    broker.client.call('COC.EVENT',{'task_id':task['id'],'kind':'provider.usage','provider':'openai','usage':result['usage'],'response_id':result['provider_response_id']})
    (ROOT/'evidence/integration/live-openai.json').write_text(json.dumps({'mode':'LIVE PAID API','provider_result':result,'host_result':finished,'capabilities':provider.capabilities(),'budget_records':ledger.records()},indent=2))
