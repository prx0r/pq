from __future__ import annotations
from dataclasses import dataclass
from heapq import heappush,heappop
from typing import Iterable
from .processor import ProcessorManifest
from .registry import ProcessorRegistry
from .canonical import obj_id

@dataclass(frozen=True)
class ProofNeed:
    id:str
    required_capabilities:tuple[str,...]
    proof_class:str="Q2"
    external:bool=False
    consequential:bool=False
    weight:float=1.0

@dataclass(frozen=True)
class PlanPolicy:
    allow_network_reads:bool=True
    allow_workspace_writes:bool=True
    allow_external_writes:bool=False
    allow_human_attention:bool=True
    max_money:float|None=None
    max_wall_seconds:float|None=None
    max_human_seconds:float|None=None

@dataclass(frozen=True)
class ProcessorPlan:
    proof_need_id:str
    processors:tuple[str,...]
    capabilities:tuple[str,...]
    estimated_money:float
    estimated_wall_seconds:float
    estimated_human_seconds:float
    authority_required:bool
    plan_id:str


def _burden(m:ProcessorManifest, human_weight=1/60):
    c=m.cost
    return 1.0+c.money+c.wall_seconds/60+c.human_seconds*human_weight+c.uncertainty

def _allowed(m:ProcessorManifest,need:ProofNeed,policy:PlanPolicy):
    eff=set(m.side_effects)
    if "network-read" in eff and not policy.allow_network_reads:return False
    if "workspace-write" in eff and not policy.allow_workspace_writes:return False
    if "human-attention" in eff and not policy.allow_human_attention:return False
    # Consequential effects may never be pulled into a non-consequential proof plan.
    if "external-write" in eff and not (policy.allow_external_writes and need.consequential):return False
    return True


def plan_processors(need:ProofNeed, registry:ProcessorRegistry, *, initial_capabilities:Iterable[str]=(), max_steps:int=8, exploration_bias:dict[str,float]|None=None, policy:PlanPolicy|None=None)->ProcessorPlan:
    """Uniform-cost search over capability states.

    Processors produce proof progress/evidence, never proof validity. External writes are
    structurally unavailable unless both the proof need is consequential and policy opts in.
    """
    initial=frozenset(initial_capabilities);target=set(need.required_capabilities);bias=exploration_bias or {};policy=policy or PlanPolicy()
    if target<=set(initial):
        pid=obj_id("processor-plan",{"need":need.id,"processors":[]})
        return ProcessorPlan(need.id,(),tuple(sorted(initial)),0,0,0,False,pid)
    q=[];heappush(q,(0.0,0,(),initial,0.0,0.0,0.0));seen={initial:0.0}
    chosen=None
    while q:
        score,steps,path,caps,money,wall,human=heappop(q)
        if target<=set(caps):chosen=(path,caps,money,wall,human);break
        if steps>=max_steps:continue
        for m in registry.all():
            if not _allowed(m,need,policy):continue
            if not set(m.requires)<=set(caps):continue
            new=frozenset(set(caps)|set(m.provides))
            if new==caps:continue
            nm=money+m.cost.money;nw=wall+m.cost.wall_seconds;nh=human+m.cost.human_seconds
            if policy.max_money is not None and nm>policy.max_money:continue
            if policy.max_wall_seconds is not None and nw>policy.max_wall_seconds:continue
            if policy.max_human_seconds is not None and nh>policy.max_human_seconds:continue
            extra=_burden(m)*float(bias.get(m.id,1.0));ns=score+extra
            if ns+1e-12>=seen.get(new,float("inf")):continue
            seen[new]=ns;heappush(q,(ns,steps+1,path+(m.id,),new,nm,nw,nh))
    if chosen is None:raise ValueError(f"no-processor-plan:{need.id}:missing={sorted(target-set(initial))}")
    path,caps,money,wall,human=chosen;ms=[registry.get(x) for x in path]
    auth=need.consequential or any(x.authority_required for x in ms)
    pid=obj_id("processor-plan",{"need":need.id,"processors":path,"caps":sorted(caps),"authority":auth})
    return ProcessorPlan(need.id,path,tuple(sorted(caps)),money,wall,human,auth,pid)
