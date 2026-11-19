import json
import urllib.error
import urllib.request
import pytest
from coc import Client
from coc.control import Controller
from coc.secrets import SecretStore
from conftest import ROOT

def test_one_use_panel_ticket_and_revocation(broker):
    code=broker.client.call('COC.AUTHENTICATE',{'action':'panel_ticket'})
    def exchange(origin):
        request=urllib.request.Request(broker.url+'/session/exchange',json.dumps({'ticket':code['ticket']}).encode(),{'Content-Type':'application/json','Origin':origin})
        with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
    with pytest.raises(urllib.error.HTTPError):exchange('https://unrelated.invalid')
    session=exchange(broker.url);assert Client(broker.url,session['token'],session['agent']).call('COC.HELLO')['principal']=='operator'
    with pytest.raises(urllib.error.HTTPError):exchange(broker.url)

def test_private_secret_storage_and_controller_lifecycle(tmp_path):
    directory=tmp_path/'private';store=SecretStore(directory);secret=store.get_or_create('test-secret')
    assert secret==SecretStore(directory).get_or_create('test-secret')
    import os
    if os.name=='nt':assert secret.encode() not in next(directory.iterdir()).read_bytes()
    controller=Controller(ROOT,tmp_path/'installation')
    try:
        started=controller.start(port=0);assert started['status']=='STARTED'
        state=controller.status();assert state['status']=='RUNNING' and state['snapshot']['integrity_verified']
        assert controller.stop()['status']=='STOPPED'
        assert controller.status()['status']=='STOPPED_OR_UNAVAILABLE'
        controller.start(port=0);assert controller.status()['snapshot']['integrity_verified']
    finally:controller.stop()
