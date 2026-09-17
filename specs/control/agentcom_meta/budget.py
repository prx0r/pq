from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from contextlib import contextmanager
try: import fcntl
except ImportError: fcntl=None

class PersistentBudgetLedger:
    """Process-safe file-backed budget reservations on POSIX. Not a distributed DB."""
    def __init__(self,path:str|Path,limits:dict[str,float]):
        self.path=Path(path);self.lock_path=self.path.with_suffix(self.path.suffix+".lock")
        self.path.parent.mkdir(parents=True,exist_ok=True);self.lock_path.touch(exist_ok=True)
        if not self.path.exists():self._write({"limits":{k:float(v) for k,v in limits.items()},"used":{k:0.0 for k in limits},"reservations":{}})
    @contextmanager
    def _locked(self):
        with self.lock_path.open("r+") as f:
            if fcntl:fcntl.flock(f.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:
                if fcntl:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    def _read(self):return json.loads(self.path.read_text())
    def _write(self,d):
        fd,tmp=tempfile.mkstemp(prefix=self.path.name+".",dir=self.path.parent);os.close(fd)
        Path(tmp).write_text(json.dumps(d,sort_keys=True,separators=(",",":")))
        os.replace(tmp,self.path)
    def reserve(self,rid:str,**amounts):
        with self._locked():
            d=self._read()
            if rid in d["reservations"]:return False,"duplicate-reservation"
            for k,v in amounts.items():
                if k not in d["limits"]:return False,f"unknown-budget:{k}"
                if float(v)<0:return False,f"negative-budget:{k}"
                pending=sum(float(r.get(k,0)) for r in d["reservations"].values())
                if d["used"][k]+pending+float(v)>d["limits"][k]+1e-12:return False,f"budget-exceeded:{k}"
            d["reservations"][rid]={k:float(v) for k,v in amounts.items()};self._write(d);return True,"reserved"
    def commit(self,rid:str):
        with self._locked():
            d=self._read();r=d["reservations"].pop(rid)
            for k,v in r.items():d["used"][k]+=float(v)
            self._write(d);return dict(d["used"])
    def release(self,rid:str):
        with self._locked():
            d=self._read();d["reservations"].pop(rid,None);self._write(d)
    def snapshot(self):
        with self._locked():return self._read()
