from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import math, hashlib, json

@dataclass(frozen=True)
class ModelOffer:
    model_id: str
    provider: str
    input_per_million: float
    output_per_million: float
    cached_input_per_million: float | None = None
    context_tokens: int | None = None
    latency_ms: float | None = None
    free_tier: bool = False
    evidence_ids: tuple[str,...] = ()
    observed_at: str | None = None

@dataclass(frozen=True)
class TaskProfile:
    proof_family: str
    processor_kind: str
    expected_input_tokens: int
    expected_output_tokens: int
    min_context_tokens: int = 0
    max_latency_ms: float | None = None
    risk_band: str = "LOW"
    human_minute_cost_usd: float = 1.0
    repair_cost_usd: float = 0.0
    value_of_success_usd: float | None = None
    tags: tuple[str,...] = ()

@dataclass
class RouteEvidence:
    model_id: str
    proof_family: str
    processor_kind: str
    successes: int = 0
    failures: int = 0
    total_cost_usd: float = 0.0
    total_human_minutes: float = 0.0
    total_wall_seconds: float = 0.0

    @property
    def alpha(self): return 1 + self.successes
    @property
    def beta(self): return 1 + self.failures
    @property
    def mean_success(self): return self.alpha/(self.alpha+self.beta)
    @property
    def n(self): return self.successes+self.failures

@dataclass(frozen=True)
class ModelRouteDecision:
    model_id: str
    provider: str
    expected_inference_cost_usd: float
    p_verified_success: float
    expected_attempts: float
    expected_cost_to_verified_completion_usd: float
    exploration_bonus: float
    score: float
    rationale: tuple[str,...]
    evidence_ids: tuple[str,...]

class VerifiedCompletionRouter:
    """QDW/LiveLLM-style model economics router.

    Price per token is only one term. We minimize expected *verified completion*
    cost using live price facts and empirical pass/fail history per proof family
    and processor kind.

    The exploration bonus is deliberately small and auditable. It encourages
    information gathering for under-tested models without allowing a cheap,
    unknown model to dominate high-risk work automatically.
    """
    def __init__(self, *, exploration_weight: float = 0.10):
        self.exploration_weight=exploration_weight
        self.history: dict[tuple[str,str,str],RouteEvidence]={}

    def record(
        self, *, model_id:str, proof_family:str, processor_kind:str,
        success:bool, cost_usd:float, human_minutes:float=0,
        wall_seconds:float=0
    ):
        k=(model_id,proof_family,processor_kind)
        ev=self.history.setdefault(k,RouteEvidence(model_id,proof_family,processor_kind))
        if success: ev.successes+=1
        else: ev.failures+=1
        ev.total_cost_usd += float(cost_usd)
        ev.total_human_minutes += float(human_minutes)
        ev.total_wall_seconds += float(wall_seconds)

    def _inference_cost(self, offer:ModelOffer, task:TaskProfile)->float:
        return (
            task.expected_input_tokens/1_000_000*offer.input_per_million
            + task.expected_output_tokens/1_000_000*offer.output_per_million
        )

    def _evidence(self,offer,task):
        return self.history.get(
            (offer.model_id,task.proof_family,task.processor_kind),
            RouteEvidence(offer.model_id,task.proof_family,task.processor_kind)
        )

    def decide(self, offers:list[ModelOffer], task:TaskProfile)->list[ModelRouteDecision]:
        rows=[]
        for offer in offers:
            if offer.context_tokens is not None and offer.context_tokens < task.min_context_tokens:
                continue
            if task.max_latency_ms is not None and offer.latency_ms is not None and offer.latency_ms > task.max_latency_ms:
                continue

            inf=self._inference_cost(offer,task)
            ev=self._evidence(offer,task)
            p=max(0.05,min(0.995,ev.mean_success))
            attempts=1/p
            avg_h=(ev.total_human_minutes/ev.n) if ev.n else 0.0
            expected=attempts*(inf+task.repair_cost_usd+avg_h*task.human_minute_cost_usd)

            # Confidence-aware exploration: more uncertainty -> lower ranking cost,
            # but suppress it for high-risk work.
            uncertainty=math.sqrt((p*(1-p))/(ev.n+3))
            risk_mult={"LOW":1.0,"MEDIUM":0.5,"HIGH":0.15,"CRITICAL":0.0}.get(task.risk_band,0.5)
            bonus=self.exploration_weight*uncertainty*risk_mult
            score=expected*(1-bonus)
            rows.append(ModelRouteDecision(
                model_id=offer.model_id,provider=offer.provider,
                expected_inference_cost_usd=inf,
                p_verified_success=p,
                expected_attempts=attempts,
                expected_cost_to_verified_completion_usd=expected,
                exploration_bonus=bonus,
                score=score,
                rationale=(
                    "live price fact + empirical verified outcomes",
                    "optimized for cost-to-verified-completion, not token price",
                    "unknown models receive Beta(1,1) prior and bounded exploration",
                ),
                evidence_ids=offer.evidence_ids,
            ))
        return sorted(rows,key=lambda x:x.score)

    def choose(self,offers,task):
        rows=self.decide(offers,task)
        return rows[0] if rows else None
