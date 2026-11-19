"""Independent fixed oracle; the repair tool cannot modify this file."""
import json
import sys
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('report_under_test',Path(sys.argv[1]))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
results=[]
for values,expected in [([10,20,30],20),([7],7),([-2,2],0),([1.5,2.5],2)]:
    try:
        actual=module.report_average(values)
        results.append({'values':values,'expected':expected,'actual':actual,'passed':actual==expected})
    except Exception as exc:results.append({'values':values,'error':type(exc).__name__,'passed':False})
try:module.report_average([]);results.append({'empty_rejected':False,'passed':False})
except ValueError:results.append({'empty_rejected':True,'passed':True})
print(json.dumps({'passed':all(r['passed'] for r in results),'cases':results}))
sys.exit(0 if all(r['passed'] for r in results) else 1)
