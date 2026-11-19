import threading
import pytest
from coc.providers import Policy,UsageLedger,BudgetExceeded,configured_provider,HTTPProvider

def test_durable_request_limit_and_unknown_reservation(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite',Policy(max_requests=1))
    request=ledger.reserve('test','fixture',40,20)
    with pytest.raises(BudgetExceeded):ledger.reserve('test','fixture',1,1)
    ledger.finish(request,'outcome_unknown')
    restarted=UsageLedger(tmp_path/'usage.sqlite',Policy(max_requests=1))
    with pytest.raises(BudgetExceeded):restarted.reserve('test','fixture',1,1)

def test_monetary_limit_and_origin_binding(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite',Policy(max_usd=0,input_usd_per_million=1,output_usd_per_million=1))
    with pytest.raises(BudgetExceeded):ledger.reserve('test','fixture',1,1)
    with pytest.raises(ValueError):HTTPProvider('openai','https://unrelated.invalid/v1','fixture',ledger)
    with pytest.raises(ValueError):HTTPProvider('local','http://localhost:80@unrelated.invalid','fixture',ledger,local=True)
    with pytest.raises(RuntimeError):configured_provider({'provider':'manus','model':'unknown'},ledger)

def test_concurrent_admission_is_atomic(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite',Policy(max_concurrent=1));accepted=[]
    def reserve():
        try:accepted.append(ledger.reserve('fixture','fixture',1,1))
        except BudgetExceeded:pass
    threads=[threading.Thread(target=reserve) for _ in range(8)]
    for thread in threads:thread.start()
    for thread in threads:thread.join()
    assert len(accepted)==1
