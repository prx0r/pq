from __future__ import annotations
from dataclasses import dataclass
from .models import Cost,ProofGap

PROOF_TYPES={
 'structural':('qdw.replay','proof.construct','proof.verify'),
 'build':('build.sandbox','test.hidden','proof.construct','proof.verify'),
 'external_actuality':('oracle.query','proof.construct','proof.verify'),
 'formal_math':('formal.lean','proof.construct','proof.verify'),
 'performance':('harbor.rollout','harbor.evaluate','test.hidden','proof.construct','proof.verify'),
 'economic_action':('livellm.catalog','gabs.model_route','escalation.request','human.grant_review','proof.construct','proof.verify'),
 'human_exclusive':('escalation.request','human.resolve_block','proof.construct','proof.verify'),
 'uncertainty':('prior.retrieve','web.search','cg.world_simulate','redteam.falsify','proof.construct','proof.verify'),
 'optimization':('prior.retrieve','cg.world_simulate','cg.evolve','optimize.search','harbor.rollout','test.hidden','proof.construct','proof.verify'),
 'exploration':('prior.retrieve','web.search','cg.world_simulate','harbor.rollout','module.design','test.hidden','proof.construct','proof.verify'),
 'repair':('prior.retrieve','redteam.falsify','repair.failure','test.hidden','proof.construct','proof.verify'),
}

@dataclass(frozen=True)
class ProofObligation:
    id:str; statement:str; proof_type:str; problem_type:str; value_milli:int=1000; information_gain_milli:int=0; hard:bool=True

@dataclass(frozen=True)
class ProcessorFitness:
    processor_id:str; resolve_probability_milli:int; expected_cost:Cost; information_gain_milli:int; reuse_milli:int; score_micro:int

def canonical_recipe(proof_type):
    if proof_type not in PROOF_TYPES: return PROOF_TYPES['uncertainty']
    return PROOF_TYPES[proof_type]

def fitness(processor_id,*,p_resolve_milli,value_milli,ig_milli,reuse_milli,cost_minor,tokens,wall_ms):
    # Integer-only proxy for E[verified state delta] / resource burden.
    numerator=max(1,p_resolve_milli)*max(1,value_milli)*(1000+max(0,ig_milli))*(1000+max(0,reuse_milli))
    burden=1+max(0,cost_minor)*1000+max(0,tokens)//10+max(0,wall_ms)//10
    return numerator//burden

def compose_budget(registry,processor_ids):
    c=Cost()
    for pid in processor_ids: c=c+registry.get(pid).cost
    return c
