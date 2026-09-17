from __future__ import annotations
from dataclasses import dataclass
from .compiler import assemble
from .experiment import DEFAULT_LANES,LaneRun
from .planner import ProofNeed
from .registry import ProcessorRegistry

POLICY_BIASES={
 'reuse-first':{'processor.reuse.gitgoblin':0.55,'processor.build.code':1.2},
 'proof-first':{'processor.probe.oracle':0.6,'processor.search.web':1.1},
 'search-first':{'processor.search.web':0.55,'processor.analyze.problem_graph':0.7},
 'simulation-first':{'processor.simulate.world':0.5,'processor.search.web':1.05},
 'replacement':{'processor.repair.code':1.4,'processor.search.web':0.8,'processor.simulate.world':0.8},
}

def compile_five_lanes(contract_root:str,proof_root:str,needs:list[ProofNeed],registry:ProcessorRegistry,*,initial_capabilities=()):
    rows=[]
    for lane in DEFAULT_LANES:
        a=assemble(contract_root,proof_root,needs,registry,initial_capabilities=initial_capabilities,exploration_bias=POLICY_BIASES.get(lane.policy))
        rows.append({'lane':lane,'assembly':a})
    return rows
