from __future__ import annotations
from dataclasses import dataclass,field
from typing import Callable
from .canonical import obj_id
from .memory import RunMemory,RunBank

@dataclass(frozen=True)
class LaneSpec:
    id:str
    policy:str
    mutation:str
    exploration:bool=False

@dataclass
class LaneRun:
    lane:LaneSpec
    contract_root:str
    proof_root:str
    qp_valid:bool
    actuality:str
    money:float
    wall_seconds:float
    human_seconds:float
    processor_ids:tuple[str,...]
    failure_codes:tuple[str,...]=()
    evidence_refs:tuple[str,...]=()
    trajectory:list[dict]=field(default_factory=list)
    artifacts:tuple[str,...]=()
    reusable_assets:tuple[str,...]=()
    def run_memory(self):
        return RunMemory(self.lane.id,(self.contract_root,self.proof_root),self.processor_ids,self.qp_valid,self.actuality,self.money,self.wall_seconds,self.human_seconds,self.failure_codes,self.reusable_assets)

DEFAULT_LANES=(
    LaneSpec("lane:reuse","reuse-first","prefer-verified-assets"),
    LaneSpec("lane:proof","proof-first","probe-before-build"),
    LaneSpec("lane:search","search-first","expand-solution-space",True),
    LaneSpec("lane:simulate","simulation-first","world-model-before-effect",True),
    LaneSpec("lane:replace","replacement","mutate-architecture",True),
)

class FiveLaneLab:
    def __init__(self,runbank:RunBank|None=None):self.runbank=runbank or RunBank()
    def run(self,contract_root:str,proof_root:str,executor:Callable[[LaneSpec],LaneRun],lanes=DEFAULT_LANES):
        if len(lanes)!=5:raise ValueError("five-lane-lab-requires-five")
        runs=[executor(l) for l in lanes]
        if {r.contract_root for r in runs}!={contract_root}:raise ValueError("contract-root-drift")
        if {r.proof_root for r in runs}!={proof_root}:raise ValueError("proof-root-drift")
        # Correctness lexicographically dominates economics.
        good=[r for r in runs if r.qp_valid and r.actuality=="TRUE"]
        ranked=sorted(good,key=lambda r:(r.money,r.human_seconds,r.wall_seconds,len(r.failure_codes),r.lane.id))
        for r in runs:self.runbank.add(r.run_memory())
        return {"winner":ranked[0].lane.id if ranked else None,"ranked":[r.lane.id for r in ranked],"rejected":[r.lane.id for r in runs if r not in good],"runs":runs,
                "experiment_id":obj_id("experiment",{"contract_root":contract_root,"proof_root":proof_root,"lanes":[r.lane.id for r in runs]})}
