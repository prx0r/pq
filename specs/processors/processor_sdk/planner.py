from __future__ import annotations
from dataclasses import asdict
from typing import Any
from .model import ProcessorPlan, ProcessorSpec
from .registry import ProcessorRegistry
from .packs import RuntimePackRegistry
from run_memory import RunStore

class ProcessorPlanner:
    def __init__(
        self,
        registry: ProcessorRegistry,
        packs: RuntimePackRegistry,
        history: RunStore | None = None,
    ):
        self.registry=registry
        self.packs=packs
        self.history=history

    def _estimate(self, spec: ProcessorSpec) -> dict[str,Any]:
        return asdict(spec.default_estimate)

    def plan(
        self, *,
        contract_root: str,
        obligation_id: str,
        tags: set[str],
        proof_family: str,
        available_capabilities: set[str],
        budget_usd: float | None,
    ) -> ProcessorPlan:
        candidates=[]
        for spec in self.registry.matching(tags):
            required=set(spec.capabilities)
            if not required.issubset(available_capabilities):
                continue
            est=spec.default_estimate.usd
            if budget_usd is not None and est is not None and est>budget_usd:
                continue
            candidates.append(spec)

        foundations=[]
        if self.history:
            for score,run in self.history.similar(
                tags=tags,proof_family=proof_family,top_k=3
            ):
                foundations.append(run.run_id)

        def score(spec: ProcessorSpec):
            est=spec.default_estimate
            dollars=0 if est.usd is None else est.usd
            seconds=0 if est.wall_seconds is None else est.wall_seconds
            # History/reuse/search/probe before BUILD is intentional.
            kind_bias={
                "RETRIEVE":-5,"SEARCH":-3,"DISCOVER":-2.5,"PROBE":-2,
                "DECOMPOSE":-1,"TEST":-.5,"SIMULATE":0,"BUILD":2,
                "RED_TEAM":1,"REPAIR":1.5,"OPTIMIZE":3,"MUTATE":3
            }.get(spec.kind,0)
            return kind_bias + dollars + seconds/300

        candidates=sorted(candidates,key=score)
        selected=candidates[0] if candidates else None
        fallback=selected.fallback_pack if selected else "proof.stuck"
        return ProcessorPlan(
            contract_root=contract_root,
            obligation_id=obligation_id,
            candidate_processors=[x.id for x in candidates],
            selected_processor=selected.id if selected else None,
            fallback_pack=fallback,
            estimated=self._estimate(selected) if selected else {},
            historical_foundations=foundations,
            rationale=[
                "proof meaning is frozen outside processor planner",
                "reuse/retrieval/probe precede build when admissible",
                "processor cannot settle its own output",
            ],
        )
