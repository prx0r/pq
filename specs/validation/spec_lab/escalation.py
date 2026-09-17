from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .models import EscalationClaim
from .policies import KernelPolicy, FINAL_POLICY

@dataclass
class CapabilityGraph:
    machine: set[str] = field(default_factory=set)
    human: set[str] = field(default_factory=set)
    authorized: set[str] = field(default_factory=set)

@dataclass
class BlockResolution:
    outcome: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)

def resolve_block(
    claim: EscalationClaim,
    graph: CapabilityGraph,
    *,
    attempt_evidence: list[str] | None = None,
    retry_minimum: int = 1,
    max_cost_usd: float = 0.0,
    policy: KernelPolicy = FINAL_POLICY,
) -> BlockResolution:
    attempt_evidence = list(attempt_evidence or [])
    req = claim.requirement

    # Old architecture: trust model-selected H/M kind. Kept only for convergence.
    if not policy.reject_direct_escalation_types:
        if claim.blocker_class == "human":
            return BlockResolution("H_TASK", "model_declared_human", {"parent_atask": claim.parent_atask_id})
        if claim.blocker_class == "money":
            return BlockResolution("M_TASK", "model_declared_money", {"parent_atask": claim.parent_atask_id})

    machine = req in graph.machine
    human = req in graph.human
    authorized = req in graph.authorized
    alternatives = claim.alternatives_checked
    exhausted = bool(alternatives) and all(
        x.get("status") in {"FAILED", "UNAVAILABLE", "OUT_OF_POLICY"}
        for x in alternatives
    )

    structural = claim.blocker_class in {"physical", "identity", "owner_reserved"}
    enough_attempts = structural or len(attempt_evidence) >= retry_minimum

    if human and not machine and exhausted and enough_attempts:
        return BlockResolution("H_TASK", "human_exclusive", {
            "parent_atask": claim.parent_atask_id,
            "requirement": req,
            "evidence_ids": sorted(set(claim.evidence_ids + attempt_evidence)),
            "alternatives_checked": alternatives,
            "expected_artifact": f"artifact:{req}",
        })

    gain = float(claim.estimated_gain or 0)
    requested = float(claim.requested_cost_usd or 0)
    if machine and not authorized and exhausted and enough_attempts:
        if gain > 0 and requested <= max_cost_usd:
            return BlockResolution("M_TASK", "machine_capability_not_authorized", {
                "parent_atask": claim.parent_atask_id,
                "resource": req,
                "requested_cost_usd": requested,
                "expected_gain": gain,
                "alternatives_checked": alternatives,
            })
        return BlockResolution("REPLAN", "money_not_justified")

    if machine and not enough_attempts:
        return BlockResolution("CONTINUE", "insufficient_attempt_evidence")

    if machine and authorized:
        return BlockResolution("CONTINUE", "capability_already_authorized")

    if not machine and not human:
        return BlockResolution("FAIL", "capability_unavailable")

    return BlockResolution("REPLAN", "block_not_certified")
