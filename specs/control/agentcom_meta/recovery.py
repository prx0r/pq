from __future__ import annotations
from dataclasses import dataclass
from .registry import ProcessorRegistry
from .planner import ProofNeed,plan_processors

@dataclass(frozen=True)
class FailureSignal:
    proof_id:str
    actuality:str
    code:str
    detail:str=""

RECOVERY_TARGETS={
    "MISSING_EVIDENCE":("evidence.external",),
    "UNKNOWN_MECHANISM":("solution.candidates",),
    "IMPLEMENTATION_DEFECT":("artifact.repaired",),
    "DEPENDENCY_MISSING":("component.reusable",),
    "BUDGET_PRESSURE":("route.optimized",),
    "HUMAN_BOUNDARY":("human.decision",),
    "REPEATED_FAILURE":("alternative.mechanism",),
    "NEEDS_WORLD_MODEL":("simulation.outcome",),
}

def recovery_plan(signal:FailureSignal,registry:ProcessorRegistry,*,initial=(),exploration=False):
    targets=RECOVERY_TARGETS.get(signal.code)
    if not targets:raise ValueError(f"unknown-recovery-code:{signal.code}")
    bias={}
    if exploration:
        # Slightly penalize the canonical cheapest route to force a different mechanism.
        for m in registry.all():
            if "explore" not in m.fallback_tags:bias[m.id]=1.25
    return plan_processors(ProofNeed(f"recovery:{signal.proof_id}:{signal.code}",targets),registry,initial_capabilities=initial,exploration_bias=bias)
