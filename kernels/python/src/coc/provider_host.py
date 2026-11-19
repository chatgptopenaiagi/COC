"""Provider-neutral specialist host with broker-mediated tool execution."""
import argparse
import json
from pathlib import Path
from .client import Client
from .host import HostAdapter,capability
from .providers import Policy,UsageLedger,configured_provider

class ProviderHost(HostAdapter):
    def __init__(self,client,provider,allowed):
        self.provider=provider;self.allowed=allowed
        descriptor=capability('agent.run','Bounded provider inference and explicit host delegation',{'type':'object','properties':{'prompt':{'type':'string','maxLength':8000}},'required':['prompt'],'additionalProperties':False},{'type':'object','required':['provider','tool_results']},idempotent=False)
        super().__init__(client,'provider-'+provider.name,'Specialist '+provider.name,{'agent.run':(descriptor,self.reason)})
    def register(self):
        self.client.call('COC.REGISTER',{'kind':'agent','name':self.name,'provider':self.provider.name})
        return super().register()
    def reason(self,args,cancelled,parent):
        if parent['budget']['reserved_tokens']<1024:raise ValueError('explicit token reservation required')
        mapping={};tools=[]
        for host in self.client.discover_capabilities()['hosts']:
            for cap in host['capabilities']:
                if (host['id'],cap['name']) not in self.allowed:continue
                name='coc_'+str(len(mapping)+1);mapping[name]=(host['id'],cap['name'])
                tools.append({'name':name,'description':host['id']+'.'+cap['name']+': '+cap['description'],'input_schema':cap['input_schema']})
        result=self.provider.generate(args['prompt'],tools=tools if self.provider.tool_calling else None,cancelled=cancelled,max_output_tokens=min(512,self.provider.ledger.policy.max_output_tokens))
        receipts=[]
        if len(result['tool_calls'])>4:raise ValueError('provider exceeded four-tool task budget')
        for call in result['tool_calls']:
            if cancelled.is_set():raise InterruptedError()
            if call['name'] not in mapping:raise PermissionError('model requested an unexposed tool')
            host,tool=mapping[call['name']]
            task=self.client.submit(host,tool,call['arguments'],parent_id=parent['id'],key=result['ledger_id']+':'+call['id'])
            receipts.append(self.client.wait(task['id'],60))
        result['tool_results']=receipts
        self.client.call('COC.EVENT',{'task_id':parent['id'],'kind':'provider.usage','provider':result['provider'],'usage':result['usage'],'ledger_id':result['ledger_id']})
        return result
    def usage_tokens(self,result):
        usage=result.get('usage') or {}
        return usage.get('total_tokens',usage.get('input_tokens',0)+usage.get('output_tokens',0))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    if 'policy' not in config:raise SystemExit('an explicit provider request/spending policy is required')
    ledger=UsageLedger(config['ledger'],Policy(**config['policy']))
    provider=configured_provider(config,ledger)
    host=ProviderHost(Client.from_env(),provider,{tuple(pair) for pair in config.get('allowed_tools',[])})
    host.run()
if __name__=='__main__':main()
