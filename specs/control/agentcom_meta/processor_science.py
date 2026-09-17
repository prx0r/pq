from __future__ import annotations
from dataclasses import dataclass
from typing import Any

PROCESSOR_FAMILIES={
"transform":{"purpose":"deterministic representation change","good_for":["schema","compile","normalize"]},
"analyze":{"purpose":"derive structure without world effects","good_for":["causal graph","dependency analysis","failure localization"]},
"search":{"purpose":"expand candidate mechanism space","good_for":["exploration","unknown mechanism","research"]},
"simulate":{"purpose":"counterfactual evaluation","good_for":["worlds","design choices","high-cost alternatives"]},
"optimize":{"purpose":"choose among measurable alternatives","good_for":["routing","budget","scheduling"]},
"experiment":{"purpose":"compare policies under common contract","good_for":["Seed0","Harbor","ablation"]},
"synthesize":{"purpose":"construct candidate artifact","good_for":["code","plan","config"]},
"repair":{"purpose":"change artifact after falsified claim","good_for":["failing tests","integration defect"]},
"probe":{"purpose":"acquire independent evidence","good_for":["Q3+","external readback","freshness"]},
"route":{"purpose":"select execution provider/model/process","good_for":["QDW","LiveLLM","cost-to-verified"]},
"escalate":{"purpose":"create bounded human/machine task","good_for":["H-task","M-task","ambiguity"]},
"act":{"purpose":"cause an external consequence under authority","good_for":["Q6+","send","publish","spend"]},
"harvest":{"purpose":"extract reusable assets from settled runs","good_for":["RunBank","skills","components"]},
"reuse":{"purpose":"retrieve verified productive capital","good_for":["underengineering","known components"]}
}

PROOF_RECIPES={
"Q0":["transform"],"Q1":["transform","analyze"],"Q2":["synthesize","probe"],
"Q3":["probe"],"Q4":["experiment","probe"],"Q5":["probe","experiment"],
"Q6":["route","escalate","act","probe"],"Q7":["experiment","optimize","harvest"],
"Q8":["experiment","escalate","optimize","probe"]}

PROBLEM_RECIPES={
"optimization":["analyze","route","optimize","experiment"],
"exploration":["analyze","search","simulate","experiment"],
"unknown_mechanism":["analyze","search","simulate","synthesize","probe"],
"implementation_failure":["analyze","search","repair","probe"],
"external_truth":["probe"],
"human_boundary":["escalate"],
"consequential_action":["route","escalate","act","probe"],
"model_selection":["route","experiment"],
"reuse":["reuse","probe"],
"learning":["experiment","harvest","optimize"]}

def recipe_for(*,proof_class:str|None=None,problem_type:str|None=None)->list[str]:
    seq=[]
    if problem_type:seq.extend(PROBLEM_RECIPES.get(problem_type,[]))
    if proof_class:seq.extend(PROOF_RECIPES.get(proof_class,[]))
    return list(dict.fromkeys(seq))
