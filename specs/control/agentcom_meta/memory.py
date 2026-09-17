from __future__ import annotations
from dataclasses import dataclass,asdict
from .canonical import obj_id

@dataclass(frozen=True)
class RunMemory:
    run_id:str
    contract_features:tuple[str,...]
    processor_ids:tuple[str,...]
    qp_valid:bool
    actuality:str
    money:float
    wall_seconds:float
    human_seconds:float
    failure_codes:tuple[str,...]=()
    reusable_assets:tuple[str,...]=()
    parent_run_ids:tuple[str,...]=()

    @property
    def memory_id(self):return obj_id("run-memory",asdict(self))

def similarity(a:tuple[str,...],b:tuple[str,...])->float:
    A=set(a);B=set(b)
    if not A and not B:return 1.0
    return len(A&B)/max(1,len(A|B))

class RunBank:
    def __init__(self):self.rows=[]
    def add(self,r:RunMemory):self.rows.append(r)
    def nearest(self,features:tuple[str,...],k=5):
        rows=[(similarity(features,r.contract_features),r) for r in self.rows]
        rows.sort(key=lambda x:(-x[0],not x[1].qp_valid,x[1].money+x[1].human_seconds/60,x[1].run_id))
        return tuple(r for s,r in rows[:k] if s>0)
    def foundation(self,features:tuple[str,...]):
        c=[r for r in self.nearest(features,20) if r.qp_valid and r.actuality=="TRUE"]
        if not c:return None
        return min(c,key=lambda r:(r.money,r.human_seconds,r.wall_seconds,r.run_id))
