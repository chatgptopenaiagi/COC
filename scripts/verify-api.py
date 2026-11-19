"""Bounded diagnostic using authorized key file; prints only public status."""
import json
from pathlib import Path
from coc.providers import UsageLedger,Policy,configured_provider,ProviderError
root=Path(__file__).resolve().parents[1]
ledger=UsageLedger(root/'.runtime/openai-integration-budget.sqlite',Policy())
provider=configured_provider({'provider':'openai','model':'gpt-4.1-mini','key_file':str(root/'openai-api-key.txt')},ledger)
record={'mode':'LIVE OpenAI API diagnostic','authentication_probe':None,'inference':None}
try:
    models=provider.discover_models()
    record['authentication_probe']={'status':'authenticated','configured_model_listed':any(m.get('id')=='gpt-4.1-mini' for m in models.get('data',[]))}
except ProviderError as error:record['authentication_probe']={'status':'failed','error':str(error)}
try:record['inference']=provider.generate('Reply only COC.',max_output_tokens=16)
except ProviderError as error:record['inference']={'status':'failed','error':str(error)}
record['requests']=ledger.records()
(root/'evidence/integration/openai-diagnostic.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'authentication':record['authentication_probe'],'inference_status':record['inference'].get('status'),'error':record['inference'].get('error'),'requests_reserved':len(record['requests'])}))
