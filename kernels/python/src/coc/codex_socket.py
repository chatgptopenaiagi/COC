"""Documented Unix-control-socket attachment. Never starts or stops a server.

Local identity is the OS user plus the socket's filesystem permissions. An
endpoint is an explicit operator selection, not authority to every loaded thread.
"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import queue
import socket
import threading
import websocket
from .codex import AppServer,CodexError

def discover_endpoints(configured=()):
    paths=list(configured)+[Path.home()/'.codex/app-server-control/app-server-control.sock']
    seen=set();result=[]
    for value in paths:
        path=Path(value).resolve()
        if str(path) in seen:continue
        seen.add(str(path))
        result.append({'transport':'unix-websocket','path':str(path),'exists':path.exists(),
                       'authentication':'current OS user / socket permissions; not probed',
                       'thread_access':'requires explicitly authorized thread and workspace','automatic_attach':False})
    return result

def connect_unix(path,timeout=10):
    raw=os.fsencode(path)
    if len(raw)>107:raise ValueError('Unix socket path exceeds platform bound')
    connection=socket.socket(getattr(socket,'AF_UNIX',1),socket.SOCK_STREAM)
    try:
        if hasattr(socket,'AF_UNIX'):connection.connect(str(path))
        elif os.name=='nt':
            class SockaddrUnix(ctypes.Structure):
                _fields_=[('family',ctypes.c_ushort),('path',ctypes.c_char*108)]
            address=SockaddrUnix(1,raw)
            winsock=ctypes.WinDLL('ws2_32',use_last_error=True)
            winsock.connect.argtypes=(ctypes.c_size_t,ctypes.c_void_p,ctypes.c_int);winsock.connect.restype=ctypes.c_int
            if winsock.connect(connection.fileno(),ctypes.byref(address),ctypes.sizeof(address))!=0:raise OSError('selected Codex Unix socket is unavailable')
        else:raise OSError('Unix sockets are unavailable on this platform')
        connection.settimeout(timeout);return connection
    except Exception:connection.close();raise

class AttachedAppServer(AppServer):
    def __init__(self,path,cwd,*,allow_create=False,max_turns=3):
        # No inherited __init__: inspecting another workspace must not create directories.
        self.path=Path(path).resolve();self.cwd=Path(cwd).resolve()
        if not self.cwd.is_dir():raise ValueError('authorized workspace must exist')
        self.max_turns=max_turns;self.turns=0;self.lock=threading.RLock();self.messages=queue.Queue(maxsize=10000)
        self.pending=[];self.process=None;self.owned_threads=set();self.tool_specs={};self.initialized=None;self.usage_totals={}
        self.ws=None;self.allow_create=allow_create;self.detached=threading.Event()
    def start(self):
        if self.ws:raise CodexError('connection is already attached')
        connection=connect_unix(self.path)
        try:self.ws=websocket.create_connection('ws://localhost/',socket=connection,suppress_origin=True,timeout=10,enable_multithread=True)
        except Exception:connection.close();raise
        self.detached.clear();self.messages=queue.Queue(maxsize=10000);self.pending=[]
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
        try:
            self.initialized=self.request('initialize',{'clientInfo':{'name':'coc_attached_bridge','version':'0.1.0-alpha.1'},'capabilities':{'experimentalApi':True}})
            self.send({'method':'initialized','params':{}});return self
        except Exception:self.close();raise
    def _read(self):
        while not self.detached.is_set():
            try:
                raw=self.ws.recv()
                if not raw or len(raw)>8*1024*1024:break
                self.messages.put(json.loads(raw),timeout=2)
            except websocket.WebSocketTimeoutException:continue
            except (OSError,ValueError,websocket.WebSocketException,queue.Full):break
        try:self.messages.put_nowait({'_closed':True})
        except queue.Full:pass
    def send(self,value):
        if not self.ws or self.detached.is_set():raise CodexError('external App Server connection is detached')
        self.ws.send(json.dumps(value))
    def inspect_thread(self,thread_id):
        thread=self.request('thread/read',{'threadId':thread_id,'includeTurns':False})['thread']
        if thread['id']!=thread_id or Path(thread.get('cwd','')).resolve()!=self.cwd:raise PermissionError('thread does not belong to the explicitly selected workspace')
        # Return only selected metadata, never conversation bodies.
        return {k:thread.get(k) for k in ('id','sessionId','cwd','status','ephemeral')}
    def authorize_thread(self,thread_id):
        metadata=self.inspect_thread(thread_id);self.owned_threads.add(thread_id);return metadata
    def create_thread(self,tools,**kwargs):
        if not self.allow_create:raise PermissionError('creation of a logical thread was not configured')
        return super().create_thread(tools,**kwargs)
    def steer_existing(self,thread_id,turn_id,text,*,operator_authorized=False):
        if not operator_authorized or thread_id not in self.owned_threads:raise PermissionError('explicit selected-thread steering authority required')
        self.inspect_thread(thread_id)
        if not 1<=len(text)<=2000:raise ValueError('bounded steering message required')
        return self.request('turn/steer',{'threadId':thread_id,'expectedTurnId':turn_id,'input':[{'type':'text','text':text}]})
    def reconnect(self):
        self.close();self.start()
        # Resume only the caller's previously authorized threads, never enumerate other histories.
        return [self.resume(tid) for tid in sorted(self.owned_threads)]
    def close(self):
        self.detached.set()
        if self.ws:
            try:self.ws.close(timeout=1)
            except (OSError,websocket.WebSocketException):pass
        if hasattr(self,'reader'):self.reader.join(timeout=2)
        self.ws=None
