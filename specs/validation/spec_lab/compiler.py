from __future__ import annotations
from dataclasses import asdict
from typing import Any
from .canonical import digest
from .drivers import LLMDriver
from .models import MissionSpec, Claim, ActualityContract
from .prompts import MISSION_SYSTEM, CLAIMS_SYSTEM, ROUTES_SYSTEM
from .validation import (
    validate_mission, validate_claims, validate_scope_separation,
    validate_mission_sources, validate_budget_caps, validate_claim_source_index,
    validate_route_map, reject_secrets, ContractError
)
from .source_index import index_markdown, extract_hard_caps
from .semantic import mission_semantic_body, contract_semantic_body
from .policies import KernelPolicy, FINAL_POLICY

def _mission_from_dict(d: dict[str, Any]) -> MissionSpec:
    return MissionSpec(
        mission_id=d.get("mission_id") or "mission",
        intent=d.get("intent") or "",
        mandatory_outcomes=list(d.get("mandatory_outcomes") or []),
        constraints=list(d.get("constraints") or []),
        non_goals=list(d.get("non_goals") or []),
        budget=dict(d.get("budget") or {}),
        source_artifacts=list(d.get("source_artifacts") or []),
        ambiguities=list(d.get("ambiguities") or []),
        optional_ideas=list(d.get("optional_ideas") or []),
    )

def _claim_from_dict(d: dict[str, Any]) -> Claim:
    return Claim(
        id=d["id"],
        statement=d.get("statement", ""),
        kind=d.get("kind", "leaf"),
        mandatory=bool(d.get("mandatory", True)),
        depends_on=list(d.get("depends_on") or []),
        logic=d.get("logic", "ALL"),
        proof_id=d.get("proof_id"),
        proof_class=d.get("proof_class"),
        freshness_seconds=d.get("freshness_seconds"),
        independent_readback_required=bool(d.get("independent_readback_required", False)),
        source_refs=list(d.get("source_refs") or []),
        # Claim state is canonical truth and can never come from the LLM compiler.
        # Trusted prior receipts may be applied later by the state layer.
        state="UNKNOWN",
        routes=list(d.get("routes") or []),
    )

class SpecCompiler:
    def __init__(self, driver: LLMDriver, *, policy: KernelPolicy = FINAL_POLICY):
        self.driver = driver
        self.policy = policy

    def compile(self, raw_spec: str) -> tuple[MissionSpec, ActualityContract]:
        if self.policy.reject_secrets:
            reject_secrets(raw_spec)
        source_index = index_markdown(raw_spec)
        hard_caps = extract_hard_caps(raw_spec)

        mission_raw = self.driver.complete_json(
            stage="mission",
            system=MISSION_SYSTEM,
            user=raw_spec,
        )
        mission = _mission_from_dict(mission_raw)
        validate_mission(mission)
        if self.policy.preserve_non_goals:
            validate_scope_separation(mission)
            validate_mission_sources(mission, source_index)
        validate_budget_caps(mission, hard_caps)

        # A material ambiguity about acceptance must halt before freezing.
        if self.policy.ambiguity_gate:
            material = [a for a in mission.ambiguities if a.get("affects_acceptance")]
            if material:
                raise ContractError(f"material spec ambiguity: {material}")

        if not self.policy.preserve_non_goals:
            # Historical bad behavior retained only for convergence experiments:
            # optional ideas can leak into the executable mission.
            for idea in mission.optional_ideas:
                mission.mandatory_outcomes.append({
                    "id": "optional_" + str(abs(hash(str(idea)))),
                    "statement": str(idea),
                    "source_refs": ["optional"],
                })

        mission_body = mission_semantic_body(mission)
        mission_root = digest("mission-spec", mission_body)

        if not self.policy.claim_first:
            # v0 intentionally models the failed task-first architecture.
            claims = []
            for out in mission.mandatory_outcomes:
                claims.append(Claim(
                    id="leaf." + out["id"],
                    statement=out["statement"],
                    kind="leaf",
                    mandatory=True,
                    proof_id=None,
                    source_refs=list(out.get("source_refs") or []),
                ))
            evaluator_roots = {}
            environment = {}
        else:
            claims_raw = self.driver.complete_json(
                stage="claims",
                system=CLAIMS_SYSTEM,
                user=raw_spec,
                context={"mission": mission_body, "mission_root": mission_root},
            )
            claims = [_claim_from_dict(x) for x in claims_raw.get("claims", [])]
            evaluator_roots = dict(claims_raw.get("evaluator_roots") or {})
            environment = dict(claims_raw.get("environment") or {})

            if self.policy.require_proofs:
                validate_claims(
                    claims,
                    require_traceability=self.policy.require_traceability,
                )
                validate_claim_source_index(claims, source_index)

        # Propose realization routes after claim meaning is frozen.
        routes_raw = self.driver.complete_json(
            stage="routes",
            system=ROUTES_SYSTEM,
            user=raw_spec,
            context={
                "mission": mission_body,
                "claims": [asdict(c) for c in claims],
            },
        )
        route_map = routes_raw.get("routes", {})
        if self.policy.claim_first:
            validate_route_map(route_map, {c.id for c in claims})
        for claim in claims:
            claim.routes = list(route_map.get(claim.id) or claim.routes)

        contract_body = contract_semantic_body(
            mission_root, claims, evaluator_roots, environment
        )
        contract_root = digest("actuality-contract", contract_body)
        contract = ActualityContract(
            mission_root=mission_root,
            claims=claims,
            evaluator_roots=evaluator_roots,
            environment=environment,
            contract_root=contract_root,
        )
        return mission, contract
