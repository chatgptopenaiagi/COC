import os
import secrets
import sys
import pytest
from conftest import ROOT

def test_django_actual_broker_state_and_permissions(broker,tmp_path,monkeypatch):
    sys.path.insert(0,str(ROOT/'frameworks/django'))
    monkeypatch.setenv('COC_DJANGO_SECRET',secrets.token_urlsafe(48));monkeypatch.setenv('COC_ADMIN_DB',str(tmp_path/'django.sqlite'))
    monkeypatch.setenv('DJANGO_SETTINGS_MODULE','cocadmin.settings')
    token=broker.client.issue('django-admin',['discover','system:read','event:write'])
    monkeypatch.setenv('COC_URL',broker.url);monkeypatch.setenv('COC_ADMIN_TOKEN',token._token)
    import django;django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from django.test import Client
    call_command('migrate',verbosity=0)
    browser=Client(enforce_csrf_checks=True)
    assert browser.get('/api/snapshot').status_code==302
    staff=User.objects.create_user(username='test-operator',password=secrets.token_urlsafe(32),is_staff=True)
    browser.force_login(staff)
    response=browser.get('/api/snapshot');assert response.status_code==200
    assert response.json()['broker']['pid']==broker.process.pid
    assert browser.get('/').status_code==200
    assert browser.post('/api/control',{'action':'cancel','task_id':'unowned'}).status_code==403
    (ROOT/'evidence/integration/django.json').write_text(__import__('json').dumps({'real_broker_pid':broker.process.pid,'staff_authentication':True,'csrf_enforced':True,'live_snapshot':True}))
