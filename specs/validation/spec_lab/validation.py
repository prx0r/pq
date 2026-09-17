from __future__ import annotations
import re
from typing import Any
from .models import MissionSpec, Claim, ActualityContract
from .source_index import Section, validate_refs, classify_refs

class ContractError(ValueError):
    pass

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:API_KEY|SECRET_KEY|PRIVATE_KEY|WALLET_SEED)\s*[:=]\s*\S+", re.I),
]

def reject_secrets(text: str) -> None:
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            raise ContractError("potential secret material found in prompt/context")

def validate_mission(mission: MissionSpec) -> None:
    if not mission.intent.strip():
        raise ContractError("mission.intent required")
    if not mission.mandatory_outcomes:
        raise ContractError("at least one mandatory outcome required")
    if not isinstance(mission.budget, dict):
        raise ContractError("budget must be object")
    for item in mission.mandatory_outcomes:
        if not item.get("id") or not item.get("statement"):
            raise ContractError("mandatory outcome missing id/statement")
    mandatory_ids = {x["id"] for x in mission.mandatory_outcomes}
    if len(mandatory_ids) != len(mission.mandatory_outcomes):
        raise ContractError("duplicate mandatory outcome id")

def validate_claims(claims: list[Claim], *, require_traceability: bool = True) -> None:
    ids = [c.id for c in claims]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate claim id")
    by_id = {c.id: c for c in claims}
    roots = [c for c in claims if c.kind == "root" and c.mandatory]
    if not roots:
        raise ContractError("no mandatory root claims")
    for c in claims:
        for dep in c.depends_on:
            if dep not in by_id:
                raise ContractError(f"unknown dependency {dep} from {c.id}")
        if c.kind == "leaf":
            if c.mandatory and not c.proof_id:
                raise ContractError(f"mandatory leaf missing proof_id: {c.id}")
            if require_traceability and c.mandatory and not c.source_refs:
                raise ContractError(f"mandatory leaf missing source refs: {c.id}")
            if c.independent_readback_required and (c.proof_class or "") not in {
                "external_readback", "independent_readback", "cross_channel"
            }:
                raise ContractError(f"readback-required leaf lacks readback proof class: {c.id}")
    validate_claim_dag(claims)

def validate_contract(contract: ActualityContract) -> None:
    if not contract.contract_root.startswith("sha256:"):
        raise ContractError("contract root must be content hash")
    validate_claims(contract.claims)


def _norm_scope_text(value: Any) -> str:
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

def validate_scope_separation(mission: MissionSpec) -> None:
    """Reject obvious LLM scope drift before a MissionSpec can be frozen.

    This is intentionally conservative: the compiler is not trying to infer
    semantics from scratch here. It checks contradictions between the model's
    own mandatory/optional/non-goal classifications.
    """
    optional = {_norm_scope_text(x) for x in mission.optional_ideas if _norm_scope_text(x)}
    non_goals = {_norm_scope_text(x) for x in mission.non_goals if _norm_scope_text(x)}
    for out in mission.mandatory_outcomes:
        stmt = _norm_scope_text(out.get("statement", ""))
        oid = _norm_scope_text(out.get("id", ""))
        if stmt in optional or oid.startswith("optional "):
            raise ContractError(f"mandatory outcome collides with optional scope: {out.get('id')}")
        if stmt in non_goals:
            raise ContractError(f"mandatory outcome collides with explicit non-goal: {out.get('id')}")


ALLOWED_ROUTE_KINDS = {"ALREADY_TRUE","REUSE","CONFIGURE","INTEGRATE","BUILD","BUY","BLOCKED"}

def validate_mission_sources(mission: MissionSpec, source_index: dict[str, Section]) -> None:
    for out in mission.mandatory_outcomes:
        refs=list(out.get("source_refs") or [])
        ok,reason=validate_refs(refs,source_index)
        if not ok:
            raise ContractError(reason)
        kinds=classify_refs(refs,source_index)
        if refs and kinds and kinds.issubset({"optional","non_goal"}):
            raise ContractError(f"mandatory outcome grounded only in non-mandatory source section: {out.get('id')}")

def validate_budget_caps(mission: MissionSpec, hard_caps: dict[str,float]) -> None:
    for key,cap in hard_caps.items():
        value=mission.budget.get(key)
        if value is None:
            continue
        try:
            numeric=float(value)
        except Exception as e:
            raise ContractError(f"budget {key} must be numeric") from e
        if numeric < 0:
            raise ContractError(f"budget {key} cannot be negative")
        if numeric > float(cap):
            raise ContractError(f"budget {key} exceeds raw-spec hard cap {cap}")

def validate_claim_source_index(claims: list[Claim], source_index: dict[str,Section]) -> None:
    for c in claims:
        ok,reason=validate_refs(c.source_refs,source_index)
        if not ok:
            raise ContractError(f"{c.id}: {reason}")
        kinds=classify_refs(c.source_refs,source_index)
        if c.mandatory and c.source_refs and kinds and kinds.issubset({"optional","non_goal"}):
            raise ContractError(f"{c.id}: mandatory claim grounded only in non-mandatory section")

def validate_claim_dag(claims: list[Claim]) -> None:
    by={c.id:c for c in claims}
    temp=set()
    perm=set()
    def visit(node_id: str):
        if node_id in perm:
            return
        if node_id in temp:
            raise ContractError(f"claim dependency cycle at {node_id}")
        temp.add(node_id)
        for dep in by[node_id].depends_on:
            visit(dep)
        temp.remove(node_id)
        perm.add(node_id)
    for cid in by:
        visit(cid)

def validate_route_map(route_map: dict[str,list[dict[str,Any]]], claim_ids: set[str]) -> None:
    import math
    for claim_id,routes in route_map.items():
        if claim_id not in claim_ids:
            raise ContractError(f"routes supplied for unknown claim {claim_id}")
        if not isinstance(routes,list):
            raise ContractError(f"routes for {claim_id} must be list")
        ids=set()
        for r in routes:
            rid=r.get("id")
            if not rid or rid in ids:
                raise ContractError(f"invalid/duplicate route id for {claim_id}")
            ids.add(rid)
            kind=r.get("kind")
            if kind not in ALLOWED_ROUTE_KINDS:
                raise ContractError(f"unknown route kind {kind} for {claim_id}")
            for key in ("cost_usd","time_minutes","human_minutes","irreversibility","complexity","information_gain"):
                value=r.get(key)
                if value is None:
                    continue
                if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(float(value)):
                    raise ContractError(f"route {rid} has invalid {key}")
                if float(value)<0:
                    raise ContractError(f"route {rid} has negative {key}")

def reject_orphan_tasks(tasks: list[Any], contract: ActualityContract) -> None:
    leaf_ids = {c.id for c in contract.claims if c.kind == "leaf"}
    for t in tasks:
        if not t.covers:
            raise ContractError(f"task {t.id} covers nothing")
        unknown = [x for x in t.covers if x not in leaf_ids]
        if unknown:
            raise ContractError(f"task {t.id} covers unknown leaves {unknown}")
