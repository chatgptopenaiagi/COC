"""Small MCP stdio adapter for COC tools (protocol 2025-06-18).

Bearer token is inherited in COC_TOKEN, not in MCP messages or configuration.
Advertises only tools. No sampling, arbitrary shell, resource access, or HTTP MCP.
"""
import json
import sys
from .client import Client

class MCPBridge:
    def __init__(self,client):self.client=client;self.initialized=False;self.tools={}
    def dispatch(self,message):
        method=message.get('method');p=message.get('params',{})
        if method=='initialize':
            if p.get('protocolVersion')!='2025-06-18':raise ValueError('supported protocol: 2025-06-18')
            self.initialized=True
            return {'protocolVersion':'2025-06-18','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'coc','version':'0.1.0-alpha.2'}}
        if not self.initialized:raise PermissionError('initialize first')
        if method=='ping':return {}
        if method=='tools/list':
            self.tools={};result=[]
            for host in self.client.discover_capabilities()['hosts']:
                for cap in host['capabilities']:
                    name=host['id']+'__'+cap['name'];self.tools[name]=(host['id'],cap['name'])
                    result.append({'name':name,'description':cap['description'],'inputSchema':cap['input_schema']})
            return {'tools':result}
        if method=='tools/call':
            if p.get('name') not in self.tools:raise PermissionError('tool not advertised')
            host,tool=self.tools[p['name']]
            task=self.client.submit(host,tool,p.get('arguments',{}),key='mcp:'+str(message['id']))
            return {'content':[{'type':'text','text':json.dumps({'task_id':task['id'],'state':task['state'],'status_method':'COC.RECOVER'})}],'isError':False}
        raise ValueError('unsupported MCP method')

def main():
    bridge=MCPBridge(Client.from_env())
    for line in sys.stdin:
        if len(line)>1048576:break
        message={}
        try:
            message=json.loads(line)
            if 'id' not in message:continue
            result={'jsonrpc':'2.0','id':message['id'],'result':bridge.dispatch(message)}
        except Exception as exc:result={'jsonrpc':'2.0','id':message.get('id'),'error':{'code':-32602,'message':type(exc).__name__+': request rejected'}}
        print(json.dumps(result),flush=True)
if __name__=='__main__':main()
