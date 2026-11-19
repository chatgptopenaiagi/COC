"""A real but deliberately narrow repair lab: one arithmetic source expression.

An allowlisted AST prevents file/network/process access from generated expressions.
The model can edit the isolated report only; verification oracle is outside it.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .host import capability

class RepairLab:
    def __init__(self,workspace,examples):
        self.workspace=Path(workspace).resolve();self.workspace.mkdir(parents=True,exist_ok=True)
        self.source=self.workspace/'report.py';self.oracle=Path(examples).resolve()/'verify_report.py'
        if not self.source.exists():shutil.copyfile(Path(examples)/'defective_report.py',self.source)
    def verify(self):
        result=subprocess.run([sys.executable,'-B',str(self.oracle),str(self.source)],capture_output=True,text=True,timeout=5,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        parsed=json.loads(result.stdout)
        return {**parsed,'exit_code':result.returncode,'source_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}
    def tools(self):
        empty={'type':'object','additionalProperties':False};output={'type':'object'}
        def inspect(args,cancelled,task):return {'source':self.source.read_text(),'failure':self.verify(),'constraint':'Propose only an arithmetic expression for the return statement; values is the input list.'}
        def apply(args,cancelled,task):
            if cancelled.is_set():raise InterruptedError()
            expression=args['expression'];tree=ast.parse(expression,mode='eval')
            if len(list(ast.walk(tree)))>40:raise ValueError('expression too complex')
            allowed=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.USub,ast.UAdd,ast.Call,ast.Name,ast.Load,ast.Constant)
            for node in ast.walk(tree):
                if not isinstance(node,allowed):raise ValueError('disallowed expression')
                if isinstance(node,ast.Name) and node.id not in ('values','sum','len'):raise ValueError('disallowed name')
                if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in ('sum','len') or len(node.args)!=1 or not isinstance(node.args[0],ast.Name) or node.args[0].id!='values' or node.keywords):raise ValueError('disallowed call')
                if isinstance(node,ast.Constant) and (type(node.value) not in (int,float) or abs(node.value)>1000000):raise ValueError('bounded numeric literals only')
            original=self.source.read_bytes();backup=self.workspace/'report.original'
            if not backup.exists():backup.write_bytes(original)
            replacement="def report_average(values):\n    if not values:\n        raise ValueError('at least one value required')\n    return "+expression+'\n'
            staged=self.workspace/'report.next';staged.write_text(replacement);staged.replace(self.source)
            return {'applied':True,'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),'deployment':'not performed'}
        def verify(args,cancelled,task):return self.verify()
        return {'inspect_failure':(capability('inspect_failure','Inspect actual failing report and source in isolated repair workspace',empty,output),inspect),
                'apply_expression':(capability('apply_expression','Apply proposed arithmetic return expression in isolated workspace only',{'type':'object','properties':{'expression':{'type':'string','maxLength':256}},'required':['expression'],'additionalProperties':False},output,idempotent=True),apply),
                'verify_repair':(capability('verify_repair','Run independent fixed regression oracle against repaired source',empty,output),verify)}
