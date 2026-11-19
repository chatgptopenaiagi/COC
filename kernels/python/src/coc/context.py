"""Scoped memory in a trusted orchestrator process, separate from inference context.

The caller's identity must originate from authenticated COC principal state. This
library is not itself an authentication server. Store no credentials or PHI here.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
import uuid

KINDS={'conversation','application_state','parent_context','child_context','tool_history','task_result','verified_evidence','interpretation','checkpoint'}
class ContextStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS memory (id TEXT PRIMARY KEY,owner TEXT,task TEXT,kind TEXT,source TEXT,created REAL,expires REAL,readers TEXT,body TEXT,digest TEXT)')
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def put(self,owner,task,kind,body,source,*,readers=(),ttl=86400,receipt=None):
        if kind not in KINDS or not source or not 0<ttl<=31536000:raise ValueError('kind/source/retention required')
        if kind=='verified_evidence' and not receipt:raise ValueError('evidence requires a receipt reference; interpretation alone is insufficient')
        encoded=json.dumps({'body':body,'receipt':receipt},sort_keys=True)
        if len(encoded)>16000:raise ValueError('selective context maximum 16000 characters')
        rid=uuid.uuid4().hex;at=time.time();digest=hashlib.sha256(encoded.encode()).hexdigest()
        with self.connect() as db:db.execute('INSERT INTO memory VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,owner,task,kind,source,at,at+ttl,json.dumps(list(readers)),encoded,digest))
        return rid
    def get(self,principal,rid):
        with self.connect() as db:
            db.row_factory=sqlite3.Row;row=db.execute('SELECT * FROM memory WHERE id=?',(rid,)).fetchone()
        if not row or row['expires']<=time.time() or (principal!=row['owner'] and principal not in json.loads(row['readers'])):raise PermissionError('context unavailable to this principal')
        if hashlib.sha256(row['body'].encode()).hexdigest()!=row['digest']:raise ValueError('context integrity failure')
        return {**{k:row[k] for k in ('id','owner','task','kind','source','created','expires','digest')},**json.loads(row['body'])}
    def expire(self):
        with self.connect() as db:return db.execute('DELETE FROM memory WHERE expires<=?',(time.time(),)).rowcount
