from __future__ import annotations
from dataclasses import dataclass
from .experiment import LaneRun

@dataclass(frozen=True)
class PairComparison:
    a:str;b:str
    processor_jaccard:float
    ordered_prefix:int
    same_artifacts:bool
    same_failures:bool

def _jacc(a,b):
    A=set(a);B=set(b)
    return 1.0 if not A and not B else len(A&B)/max(1,len(A|B))

def _prefix(a,b):
    n=0
    for x,y in zip(a,b):
        if x!=y:break
        n+=1
    return n

def compare_runs(runs:list[LaneRun]):
    pairs=[]
    for i,a in enumerate(runs):
        for b in runs[i+1:]:
            pairs.append(PairComparison(a.lane.id,b.lane.id,_jacc(a.processor_ids,b.processor_ids),_prefix(a.processor_ids,b.processor_ids),a.artifacts==b.artifacts,a.failure_codes==b.failure_codes))
    unique_sequences=len({r.processor_ids for r in runs})
    unique_artifacts=len({r.artifacts for r in runs})
    return {"pairs":pairs,"unique_processor_sequences":unique_sequences,"unique_artifact_sets":unique_artifacts,"collapsed":unique_sequences==1}
