from coc.mcp import MCPBridge

def test_real_mcp_tool_admission(broker):
    broker.host('python');client=broker.client.issue('mcp-client',['discover','tool:python-science:statistics'])
    bridge=MCPBridge(client)
    hello=bridge.dispatch({'id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}})
    assert hello['capabilities']['tools']['listChanged'] is False
    listed=bridge.dispatch({'id':2,'method':'tools/list'})
    assert [t['name'] for t in listed['tools']]==['python-science__statistics']
    accepted=bridge.dispatch({'id':3,'method':'tools/call','params':{'name':'python-science__statistics','arguments':{'values':[2,4]}}})
    import json
    task=json.loads(accepted['content'][0]['text'])
    assert client.wait(task['task_id'],10)['result']['mean']==3
