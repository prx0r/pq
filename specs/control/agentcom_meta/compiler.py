from __future__ import annotations
from dataclasses import dataclass
from .planner import ProofNeed,ProcessorPlan,plan_processors
from .registry import ProcessorRegistry
from .canonical import obj_id

@dataclass(frozen=True)
class ProcessorAssembly:
    contract_root:str
    proof_root:str
    plans:tuple[ProcessorPlan,...]
    unique_processors:tuple[str,...]
    estimated_money:float
    estimated_wall_seconds:float
    estimated_human_seconds:float
    authority_required:bool
    assembly_id:str


def assemble(contract_root:str,proof_root:str,needs:list[ProofNeed],registry:ProcessorRegistry,*,initial_capabilities=(),exploration_bias=None):
    plans=tuple(plan_processors(n,registry,initial_capabilities=initial_capabilities,exploration_bias=exploration_bias) for n in needs)
    unique=tuple(dict.fromkeys(p for plan in plans for p in plan.processors))
    # Cost shared processors once at the assembly level; per-proof plans preserve attribution.
    ms=[registry.get(x) for x in unique]
    money=sum(m.cost.money for m in ms);wall=sum(m.cost.wall_seconds for m in ms);human=sum(m.cost.human_seconds for m in ms)
    auth=any(p.authority_required for p in plans)
    aid=obj_id('processor-assembly',{'contract_root':contract_root,'proof_root':proof_root,'plans':[p.plan_id for p in plans],'unique':unique})
    return ProcessorAssembly(contract_root,proof_root,plans,unique,money,wall,human,auth,aid)
