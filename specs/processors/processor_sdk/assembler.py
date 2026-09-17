from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any
from .registry import ProcessorRegistry
from .packs import RuntimePackRegistry

TEMPLATES={
    "REUSE":("history.retrieve","reuse.search","code.test"),
    "CONFIGURE":("history.retrieve","config.apply","code.test","probe.design"),
    "INTEGRATE":("history.retrieve","reuse.search","integration.compose","code.test","probe.design"),
    "BUILD":("history.retrieve","problem.decompose","code.build","code.test","redteam.falsify"),
    "BUY":("history.retrieve","tool.discover","block.resolve"),
    "BLOCKED":("block.resolve",),
}

@dataclass(frozen=True)
class ProofObligation:
    id: str
    proof_family: str
    route_kind: str
    tags: tuple[str,...]
    priority: float
    dependencies: tuple[str,...]=()

@dataclass
class ProcessorNode:
    id: str
    processor_id: str
    obligation_id: str
    depends_on: list[str]
    estimate: dict[str,Any]

@dataclass
class AssembledProcessorGraph:
    contract_root: str
    nodes: list[ProcessorNode]
    estimated_totals: dict[str,Any]
    unknown_cost_processors: list[str]
    budget_fit: bool | None
    notes: list[str]=field(default_factory=list)

def _estimate(spec, overrides):
    base=asdict(spec.default_estimate)
    base.update(overrides.get(spec.id,{}) if overrides else {})
    return base

def assemble_processor_graph(
    *,
    contract_root: str,
    obligations: list[ProofObligation],
    registry: ProcessorRegistry,
    available_capabilities: set[str],
    cost_profile: dict[str,dict[str,Any]] | None=None,
    mission_budget_usd: float | None=None,
) -> AssembledProcessorGraph:
    nodes=[]
    unknown=[]
    total_usd=0.0
    total_wall=0.0
    total_input=0
    total_output=0
    previous_by_obligation={}

    for ob in sorted(obligations,key=lambda x:-x.priority):
        template=TEMPLATES.get(ob.route_kind,("history.retrieve","problem.decompose"))
        prev=[]
        for idx,pid in enumerate(template):
            spec=registry.get(pid)
            if not set(spec.capabilities).issubset(available_capabilities):
                # Missing processor capability is not silently ignored: hand it to
                # the stuck-proof runtime pack via a marker node.
                continue
            est=_estimate(spec,cost_profile or {})
            node_id=f"proc:{ob.id}:{idx}:{pid}"
            deps=list(prev)
            for d in ob.dependencies:
                if d in previous_by_obligation:
                    deps.append(previous_by_obligation[d])
            node=ProcessorNode(node_id,pid,ob.id,sorted(set(deps)),est)
            nodes.append(node)
            prev=[node_id]
            previous_by_obligation[ob.id]=node_id

            usd=est.get("usd")
            if usd is None:
                unknown.append(pid)
            else:
                total_usd += float(usd)
            total_wall += float(est.get("wall_seconds") or 0)
            total_input += int(est.get("input_tokens") or 0)
            total_output += int(est.get("output_tokens") or 0)

    if unknown:
        budget_fit=None
    elif mission_budget_usd is None:
        budget_fit=None
    else:
        budget_fit=total_usd <= float(mission_budget_usd)

    return AssembledProcessorGraph(
        contract_root=contract_root,
        nodes=nodes,
        estimated_totals={
            "usd":None if unknown else round(total_usd,6),
            "work_seconds_sum":round(total_wall,3),
            "input_tokens":total_input,
            "output_tokens":total_output,
        },
        unknown_cost_processors=sorted(set(unknown)),
        budget_fit=budget_fit,
        notes=[
            "estimates are planning priors, not receipts",
            "unknown monetary cost remains UNKNOWN",
            "external consequences remain QP-governed",
        ],
    )
