from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal
import hashlib, json

ProcessorKind = Literal[
    "DECOMPOSE","SEARCH","DISCOVER","BUILD","TEST","PROBE","SIMULATE",
    "RED_TEAM","REPAIR","COMPARE","OPTIMIZE","MUTATE","WORLD_GENERATE",
    "RETRIEVE","ESCALATE","COMPOSE"
]

def _canonical(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _digest(tag: str, x: Any) -> str:
    return "sha256:" + hashlib.sha256(f"{tag}\0{_canonical(x)}".encode()).hexdigest()

@dataclass(frozen=True)
class ResourceEstimate:
    usd: float | None = None
    wall_seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    human_seconds: float | None = 0
    irreversible_actions: int = 0

@dataclass(frozen=True)
class ProcessorSpec:
    id: str
    version: str
    kind: ProcessorKind
    description: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    handles: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    proof_outputs: tuple[str, ...] = ()
    deterministic: bool = False
    consequence_free: bool = True
    default_estimate: ResourceEstimate = field(default_factory=ResourceEstimate)
    fallback_pack: str | None = None
    mutation_axes: tuple[str, ...] = ()
    evaluator_contract: str | None = None
    implementation_hash: str = "reference"

@dataclass
class ProcessorRun:
    processor_root: str
    processor_id: str
    contract_root: str
    proof_obligation_ids: list[str]
    inputs_root: str
    world_root: str | None
    policy_root: str
    budget: dict[str, Any]
    outputs_root: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    qp_proof_ids: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    metrics: dict[str, Any] = field(default_factory=dict)
    failure: dict[str, Any] | None = None

@dataclass
class ProcessorPlan:
    contract_root: str
    obligation_id: str
    candidate_processors: list[str]
    selected_processor: str | None
    fallback_pack: str | None
    estimated: dict[str, Any]
    historical_foundations: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

@dataclass
class ProcessorFailure:
    code: str
    processor_id: str
    obligation_id: str
    evidence_ids: list[str] = field(default_factory=list)
    retryable: bool = True
    detail: dict[str, Any] = field(default_factory=dict)

def processor_root(spec: ProcessorSpec) -> str:
    body=asdict(spec)
    return _digest("acom/processor", body)

def run_root(run: ProcessorRun) -> str:
    return _digest("acom/processor-run", asdict(run))
