from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class KernelPolicy:
    name: str
    claim_first: bool = True
    require_traceability: bool = True
    preserve_non_goals: bool = True
    reject_direct_escalation_types: bool = True
    branch_non_interference: bool = True
    shared_lane_budget: bool = True
    require_proofs: bool = True
    independent_readback: bool = True
    freeze_contract: bool = True
    unknown_cost_is_unknown: bool = True
    reject_secrets: bool = True
    idempotent_effects: bool = True
    reuse_first: bool = True
    stop_when_actuality_true: bool = True
    ambiguity_gate: bool = True
    evaluator_immutable_per_lane: bool = True

    def as_dict(self):
        return asdict(self)

VERSIONS = [
    KernelPolicy(
        "v0_task_first",
        claim_first=False, require_traceability=False, preserve_non_goals=False,
        reject_direct_escalation_types=False, branch_non_interference=False,
        shared_lane_budget=False, require_proofs=False, independent_readback=False,
        freeze_contract=False, unknown_cost_is_unknown=False, reject_secrets=False,
        idempotent_effects=False, reuse_first=False, stop_when_actuality_true=False,
        ambiguity_gate=False, evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v1_claim_first",
        require_traceability=False, preserve_non_goals=False,
        reject_direct_escalation_types=False, branch_non_interference=False,
        shared_lane_budget=False, independent_readback=False, freeze_contract=False,
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
        evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v2_trace_non_goals",
        reject_direct_escalation_types=False, branch_non_interference=False,
        shared_lane_budget=False, independent_readback=False, freeze_contract=False,
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
        evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v3_certified_escalation",
        branch_non_interference=False, shared_lane_budget=False,
        independent_readback=False, freeze_contract=False,
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
        evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v4_non_interference",
        shared_lane_budget=False, independent_readback=False, freeze_contract=False,
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
        evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v5_budgeted_lanes",
        independent_readback=False, freeze_contract=False,
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
        evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v6_actuality_readback",
        freeze_contract=False, unknown_cost_is_unknown=False, reject_secrets=False,
        idempotent_effects=False, reuse_first=False, stop_when_actuality_true=False,
        ambiguity_gate=False, evaluator_immutable_per_lane=False,
    ),
    KernelPolicy(
        "v7_frozen_evaluator",
        unknown_cost_is_unknown=False, reject_secrets=False, idempotent_effects=False,
        reuse_first=False, stop_when_actuality_true=False, ambiguity_gate=False,
    ),
    KernelPolicy(
        "v8_cost_secrets_reuse",
        idempotent_effects=False, stop_when_actuality_true=False, ambiguity_gate=False,
    ),
    KernelPolicy(
        "v9_stop_ambiguity",
        idempotent_effects=False,
    ),
    KernelPolicy("v10_fault_tolerant"),
]

FINAL_POLICY = VERSIONS[-1]
