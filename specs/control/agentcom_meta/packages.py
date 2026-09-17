from __future__ import annotations
import hashlib,json,shutil,zipfile
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PackageSpec:
    id:str
    archive:str
    role:str
    authority:str
    status:str
    canonical:bool=False
    notes:str=""

def file_sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def load_lock(path:str|Path):
    d=json.loads(Path(path).read_text())
    return tuple(PackageSpec(**x) for x in d["packages"]),d

def materialize(lock_path:str|Path,archives_dir:str|Path,outdir:str|Path):
    specs,lock=load_lock(lock_path);out=Path(outdir);out.mkdir(parents=True,exist_ok=True);results=[]
    for s in specs:
        z=Path(archives_dir)/s.archive
        if not z.exists():raise FileNotFoundError(z)
        expected=lock["sha256"].get(s.archive)
        actual=file_sha256(z)
        if expected and expected!=actual:raise ValueError(f"archive-sha-mismatch:{s.archive}")
        dst=out/s.id
        if dst.exists():shutil.rmtree(dst)
        dst.mkdir(parents=True)
        with zipfile.ZipFile(z) as f:
            names=[n for n in f.namelist() if n and not n.startswith("__MACOSX/")]
            base=dst.resolve()
            for n in names:
                target=(dst/n).resolve()
                if target!=base and base not in target.parents:
                    raise ValueError(f"unsafe-archive-path:{s.archive}:{n}")
            f.extractall(dst)
        # Historical artifacts were produced by different packagers: some are flat,
        # others contain one top-level directory. Normalize without mutating archives.
        top={n.split("/",1)[0] for n in names}
        root_files=[n for n in names if "/" not in n.rstrip("/") and not n.endswith("/")]
        if len(top)==1 and not root_files:
            inner=dst/next(iter(top))
            if inner.is_dir():
                tmp=out/(s.id+".__flat__")
                if tmp.exists():shutil.rmtree(tmp)
                inner.rename(tmp);shutil.rmtree(dst);tmp.rename(dst)
        results.append({"id":s.id,"path":str(dst),"sha256":actual})
    return results
