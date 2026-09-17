from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from qpsdk.proofcore.canonical import typed_id

@dataclass(frozen=True)
class Cost:
    money_minor:int=0; tokens:int=0; wall_ms:int=0; external_calls:int=0; human_minutes:int=0
    def __post_init__(self):
        if min(self.money_minor,self.tokens,self.wall_ms,self.external_calls,self.human_minutes)<0: raise ValueError('negative cost')
    def __add__(self,o): return Cost(*(getattr(self,k)+getattr(o,k) for k in ('money_minor','tokens','wall_ms','external_calls','human_minutes')))
    def within(self,b):
        return all(getattr(self,k)<=getattr(b,k) or getattr(b,k)==0 for k in ('money_minor','tokens','wall_ms','external_calls','human_minutes'))

@dataclass(frozen=True)
class ProcessorSpec:
    id:str; version:str; kind:str
    handles:tuple[str,...]; requires:tuple[str,...]; provides:tuple[str,...]
    # Each inner group is an OR-set: at least one capability in every group must be available.
    # This keeps evidence-polymorphic processors type-safe without weakening hard requirements.
    requires_any:tuple[tuple[str,...],...]=()
    side_effects:str='none'                 # none | sandbox | external
    determinism:str='deterministic'         # deterministic | record-replay | stochastic
    cost:Cost=field(default_factory=Cost)
    max_attempts:int=1
    description:str=''
    module_ref:str=''
    fallback:tuple[str,...]=()
    experimental:bool=False
    can_settle:bool=False
    canonical_write:bool=False
    def __post_init__(self):
        if not self.id or not self.version or not self.kind: raise ValueError('processor id/version/kind required')
        if self.side_effects not in {'none','sandbox','external'}: raise ValueError('bad side_effects')
        if self.determinism not in {'deterministic','record-replay','stochastic'}: raise ValueError('bad determinism')
        if self.max_attempts<1: raise ValueError('max_attempts')
        # Constitutional firewall: processors never settle QP truth or write canonical state.
        if self.can_settle or self.canonical_write:
            raise ValueError('processor may not settle truth or write canonical state')
        object.__setattr__(self,'handles',tuple(self.handles)); object.__setattr__(self,'requires',tuple(self.requires)); object.__setattr__(self,'provides',tuple(self.provides)); object.__setattr__(self,'requires_any',tuple(tuple(g) for g in self.requires_any)); object.__setattr__(self,'fallback',tuple(self.fallback))
        if any(not g for g in self.requires_any): raise ValueError('requires_any groups must be non-empty')

@dataclass(frozen=True)
class ProofGap:
    id:str; kind:str; requirement_id:str; statement:str; attempts:int=0; failure_signature:str=''; tags:tuple[str,...]=(); hard:bool=True

@dataclass(frozen=True)
class ProcessorRequest:
    processor_id:str; contract_root:str; gap:ProofGap; inputs:dict[str,Any]=field(default_factory=dict); budget:Cost=field(default_factory=Cost); prior_run_ids:tuple[str,...]=()

@dataclass(frozen=True)
class ProcessorOutcome:
    status:str                          # PROPOSED | OBSERVED | BLOCKED | FAILED
    evidence:tuple[dict,...]=()
    task_proposals:tuple[dict,...]=()
    artifact_refs:tuple[str,...]=()
    discovered_capabilities:tuple[str,...]=()
    notes:tuple[str,...]=()
    # Any model-supplied verdict/receipt/authorization fields are forbidden.
    def __post_init__(self):
        if self.status not in {'PROPOSED','OBSERVED','BLOCKED','FAILED'}: raise ValueError('bad status')

@dataclass(frozen=True)
class ProcessorRun:
    id:str; processor_id:str; contract_root:str; gap_id:str; input_root:str; output_root:str; cost:Cost; duration_ms:int; status:str; attempt:int; parent_run_id:str=''; proof_delta:tuple[str,...]=(); failure_signature:str=''; novelty_milli:int=0

@dataclass(frozen=True)
class ProcessorPlan:
    contract_root:str; gap_id:str; processor_ids:tuple[str,...]; estimated_cost:Cost; exploration:bool=False; reason:str=''

@dataclass(frozen=True)
class Trajectory:
    id:str; contract_root:str; spec_fingerprint:str; tags:tuple[str,...]; policy_id:str; processor_ids:tuple[str,...]; proof_ids:tuple[str,...]; verified:bool; hard_actuality:str; cost:Cost; failed_attempts:int; reusable_artifacts:tuple[str,...]=(); novelty_milli:int=0; notes:tuple[str,...]=()

def stable_id(tag,obj):
    if hasattr(obj,'__dataclass_fields__'): obj=asdict(obj)
    return typed_id(tag,obj)
