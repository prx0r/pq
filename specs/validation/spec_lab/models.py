from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Bool3 = Literal["TRUE", "FALSE", "UNKNOWN"]

@dataclass
class MissionSpec:
    mission_id: str
    intent: str
    mandatory_outcomes: list[dict[str, Any]]
    constraints: list[Any] = field(default_factory=list)
    non_goals: list[Any] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    source_artifacts: list[dict[str, Any]] = field(default_factory=list)
    ambiguities: list[dict[str, Any]] = field(default_factory=list)
    optional_ideas: list[Any] = field(default_factory=list)

@dataclass
class Claim:
    id: str
    statement: str
    kind: Literal["root", "leaf"]
    mandatory: bool
    depends_on: list[str] = field(default_factory=list)
    logic: Literal["ALL", "ANY"] = "ALL"
    proof_id: str | None = None
    proof_class: str | None = None
    freshness_seconds: int | None = None
    independent_readback_required: bool = False
    source_refs: list[str] = field(default_factory=list)
    state: Bool3 = "UNKNOWN"
    routes: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class ActualityContract:
    mission_root: str
    claims: list[Claim]
    evaluator_roots: dict[str, str]
    environment: dict[str, Any]
    contract_root: str

@dataclass
class ATask:
    id: str
    covers: list[str]
    objective: str
    route_id: str
    state: str = "READY"
    blocked_by: list[str] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    expected_actuality_delta: float = 1.0
    criticality: float = 1.0
    information_gain: float = 1.0
    cost_usd: float | None = None
    wall_minutes: float | None = None
    human_minutes: float | None = None
    irreversibility: float = 0.0
    complexity: float = 0.0

@dataclass
class Evidence:
    id: str
    claim_id: str
    probe_id: str
    observed_at: str
    value: Any
    source_class: str
    artifact_hash: str
    independent: bool = False
    environment_root: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ProofReceipt:
    id: str
    contract_root: str
    claim_id: str
    result: Bool3
    evidence_ids: list[str]
    gate_results: list[dict[str, Any]]
    state_before: str
    state_after: str
    proof_level: int = 0

@dataclass
class EscalationClaim:
    parent_atask_id: str
    blocking_operation_id: str
    requirement: str
    blocker_class: str
    evidence_ids: list[str]
    alternatives_checked: list[dict[str, Any]]
    requested_cost_usd: float | None = None
    estimated_gain: float | None = None
    model_rationale: str = ""

@dataclass
class Lane:
    id: str
    contract_root: str
    policy: str
    budget: dict[str, Any]
    stage: int = 0
    status: str = "CANDIDATE"
    metrics: dict[str, Any] = field(default_factory=dict)
    actuality: bool = False
    qp_valid: bool = False
    authority_violations: int = 0
    evaluator_root: str | None = None

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
