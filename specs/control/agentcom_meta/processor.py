from __future__ import annotations
from dataclasses import dataclass,field,asdict
from enum import Enum
from typing import Any
from .canonical import obj_id

class ProcessorStatus(str,Enum):
    PROPOSED="PROPOSED"
    EXECUTED="EXECUTED"
    BLOCKED="BLOCKED"
    FAILED="FAILED"
    TIMED_OUT="TIMED_OUT"
    REJECTED="REJECTED"

VALID_KINDS={
    "analyze","search","simulate","reuse","synthesize","repair","probe",
    "optimize","experiment","escalate","act","harvest","route","transform"
}

@dataclass(frozen=True)
class CostPrior:
    money:float=0.0
    tokens:int=0
    wall_seconds:float=0.0
    external_calls:int=0
    human_seconds:float=0.0
    uncertainty:float=0.0

@dataclass(frozen=True)
class ProcessorManifest:
    id:str
    version:str
    kind:str
    requires:tuple[str,...]=()
    provides:tuple[str,...]=()
    proof_classes:tuple[str,...]=()
    evidence_channels:tuple[str,...]=()
    side_effects:tuple[str,...]=()
    authority_required:bool=False
    deterministic:bool=True
    seed_required:bool=False
    pure:bool=False
    timeout_s:float=60.0
    cost:CostPrior=CostPrior()
    failure_codes:tuple[str,...]=()
    fallback_tags:tuple[str,...]=()
    mutation_knobs:tuple[str,...]=()
    prohibitions:tuple[str,...] = ("settle","mint-authority","self-validate")
    legacy_aliases:tuple[str,...]=()
    description:str=""

    def validate(self)->None:
        if not self.id or "." not in self.id: raise ValueError("processor-id-must-be-namespaced")
        if self.kind not in VALID_KINDS: raise ValueError(f"unknown-processor-kind:{self.kind}")
        if self.authority_required and self.kind not in {"act","escalate"}: raise ValueError("authority-required-only-act-or-escalate")
        if self.seed_required and self.deterministic: raise ValueError("deterministic-processor-cannot-require-seed")
        if self.timeout_s<=0: raise ValueError("timeout-must-be-positive")
        forbidden={"qp.settle","qp.mint_authority","proof.verdict"}
        if forbidden & set(self.provides): raise ValueError("processor-may-not-provide-sovereign-capability")
        if any(x<0 for x in (self.cost.money,self.cost.tokens,self.cost.wall_seconds,self.cost.external_calls,self.cost.human_seconds,self.cost.uncertainty)):
            raise ValueError("negative-cost-prior")

    @property
    def manifest_id(self)->str:
        d=asdict(self);return obj_id("processor",d)

@dataclass
class ProcessorContext:
    contract_root:str
    proof_root:str
    lane_id:str
    run_id:str
    capabilities:set[str]=field(default_factory=set)
    budget:dict[str,float]=field(default_factory=dict)
    metadata:dict[str,Any]=field(default_factory=dict)
    seed:int|None=None
    authority_refs:tuple[str,...]=()

@dataclass
class ProcessorResult:
    processor_id:str
    manifest_id:str
    status:ProcessorStatus
    inputs_hash:str
    outputs:dict[str,Any]=field(default_factory=dict)
    evidence:list[dict[str,Any]]=field(default_factory=list)
    capabilities_added:tuple[str,...]=()
    cost:dict[str,float]=field(default_factory=dict)
    failure_code:str|None=None
    detail:str=""
    started_at:str|None=None
    ended_at:str|None=None
    replay_hash:str|None=None

    @property
    def result_id(self)->str:
        return obj_id("processor-result",{
            "processor_id":self.processor_id,"manifest_id":self.manifest_id,"status":self.status.value,
            "inputs_hash":self.inputs_hash,"outputs":self.outputs,"evidence":self.evidence,
            "capabilities_added":self.capabilities_added,"cost":self.cost,"failure_code":self.failure_code,
            "detail":self.detail,"replay_hash":self.replay_hash,
        })
