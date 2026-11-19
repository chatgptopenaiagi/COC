import threading
import pytest
from coc.repair import RepairLab
from conftest import ROOT

def test_isolated_repair_rejects_escape_and_runs_oracle(tmp_path):
    lab=RepairLab(tmp_path,ROOT/'examples/autonomous-repair');assert lab.verify()['passed'] is False
    patch=lab.tools()['apply_expression'][1]
    for expression in ["__import__('os').getcwd()",'values.__class__','[x for x in values]','2**1000000']:
        with pytest.raises(ValueError):patch({'expression':expression},threading.Event(),{})
    patch({'expression':'sum(values) / len(values)'},threading.Event(),{})
    assert lab.verify()['passed'] is True
    assert (tmp_path/'report.original').is_file()
