import sqlite3
import pytest
from coc.context import ContextStore

def test_selective_context_provenance_and_tamper(tmp_path):
    store=ContextStore(tmp_path/'context.sqlite')
    rid=store.put('parent','task-1','interpretation',{'hypothesis':'rounding defect'},'host:report',readers=['child'])
    assert store.get('child',rid)['kind']=='interpretation'
    with pytest.raises(PermissionError):store.get('unrelated',rid)
    with pytest.raises(ValueError):store.put('parent','task-1','verified_evidence',{},'agent assertion')
    with sqlite3.connect(store.path) as db:db.execute("UPDATE memory SET body='{}'")
    with pytest.raises(ValueError):store.get('parent',rid)
