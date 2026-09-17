from __future__ import annotations
from dataclasses import asdict
from typing import Any
from .canonical import canonical_json
from .models import MissionSpec, Claim

def _sort_mixed(items: list[Any]) -> list[Any]:
    return sorted(items, key=canonical_json)

def mission_semantic_body(m: MissionSpec) -> dict[str,Any]:
    outcomes=[]
    for x in m.mandatory_outcomes:
        y=dict(x)
        if isinstance(y.get("source_refs"),list):
            y["source_refs"]=sorted(y["source_refs"])
        outcomes.append(y)
    artifacts=[dict(x) for x in m.source_artifacts]
    ambiguities=[dict(x) for x in m.ambiguities]
    return {
        "mission_id":m.mission_id,
        "intent":m.intent.strip(),
        "mandatory_outcomes":sorted(outcomes,key=lambda x:(str(x.get("id","")),canonical_json(x))),
        "constraints":_sort_mixed(list(m.constraints)),
        "non_goals":_sort_mixed(list(m.non_goals)),
        "budget":dict(m.budget),
        "source_artifacts":sorted(artifacts,key=canonical_json),
        "ambiguities":sorted(ambiguities,key=lambda x:(str(x.get("id","")),canonical_json(x))),
        "optional_ideas":_sort_mixed(list(m.optional_ideas)),
    }

def claim_semantic_body(c: Claim) -> dict[str,Any]:
    """Only acceptance semantics belong in ContractRoot.

    Excluded on purpose:
    - `state`: runtime/canonical truth changes over time;
    - `routes`: implementation proposals belong to execution planning.
    """
    return {
        "id":c.id,
        "statement":c.statement.strip(),
        "kind":c.kind,
        "mandatory":bool(c.mandatory),
        "depends_on":sorted(c.depends_on),
        "logic":c.logic,
        "proof_id":c.proof_id,
        "proof_class":c.proof_class,
        "freshness_seconds":c.freshness_seconds,
        "independent_readback_required":bool(c.independent_readback_required),
        "source_refs":sorted(c.source_refs),
    }

def contract_semantic_body(
    mission_root: str,
    claims: list[Claim],
    evaluator_roots: dict[str,str],
    environment: dict[str,Any],
) -> dict[str,Any]:
    return {
        "mission_root":mission_root,
        "claims":sorted((claim_semantic_body(c) for c in claims),key=lambda x:x["id"]),
        "evaluator_roots":dict(evaluator_roots),
        "environment":dict(environment),
    }
