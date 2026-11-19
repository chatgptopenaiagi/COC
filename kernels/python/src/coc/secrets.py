"""Project-local secrets: Windows DPAPI or owner-only Unix files.

No provider key is copied here. Only COC-generated service credentials are stored.
"""
import ctypes
import os
from pathlib import Path
import re
import secrets
import subprocess

def protect_directory(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        identity=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True).stdout
        import csv
        sid=next(csv.reader([identity.strip()]))[1]
        subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],capture_output=True,check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:path.chmod(0o700)

def _dpapi(value,encrypt):
    class Blob(ctypes.Structure):_fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=(ctypes.c_ubyte*len(value)).from_buffer_copy(value);source=Blob(len(value),buffer);destination=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(Blob)]
    function.restype=ctypes.c_int;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(destination)):raise OSError('Windows credential protection failed')
    try:return ctypes.string_at(destination.data,destination.size)
    finally:kernel.LocalFree(destination.data)

class SecretStore:
    def __init__(self,directory):self.directory=Path(directory);protect_directory(self.directory)
    def get_or_create(self,name):
        if not re.fullmatch('[a-z-]{1,32}',name):raise ValueError('invalid secret label')
        path=self.directory/(name+('.dpapi' if os.name=='nt' else '.secret'))
        if path.is_symlink():raise ValueError('secret symlinks prohibited')
        if not path.exists():
            raw=secrets.token_urlsafe(48).encode();protected=_dpapi(raw,True) if os.name=='nt' else raw
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(protected)
        data=path.read_bytes()
        return (_dpapi(data,False) if os.name=='nt' else data).decode()
