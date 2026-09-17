from __future__ import annotations
from dataclasses import asdict
from typing import Any
from .drivers import LLMDriver

CRITIC_SYSTEM = """
Independently audit the supplied technical specification for acceptance coverage.
Do not propose implementation.
List every materially mandatory obligation and its source section reference.
Also include scope/budget/human/definition-of-done obligations when they constrain
what a valid build is allowed to do.
Return JSON: {"obligations":[{"id","statement","mandatory","source_refs":[]}]}.
""".strip()

def independent_coverage_audit(
    raw_spec: str,
    mission,
    contract,
    critic_driver: LLMDriver,
) -> dict[str,Any]:
    critic=critic_driver.complete_json(
        stage="critic",
        system=CRITIC_SYSTEM,
        user=raw_spec,
        context={},
    )
    covered_refs=set()
    for out in mission.mandatory_outcomes:
        covered_refs.update(out.get("source_refs") or [])
    for c in contract.claims:
        if c.mandatory:
            covered_refs.update(c.source_refs)

    # Some source sections govern the process rather than becoming leaf claims.
    # Mission-level objects cover these classes.
    if mission.budget:
        covered_refs.add("§11")
    if mission.non_goals:
        covered_refs.add("§15")
    if mission.optional_ideas:
        covered_refs.add("§16")
    # H/M, variants, evidence and DoD are constitutional kernel behavior.
    covered_refs.update({"§12","§13","§14","§17"})

    rows=[]
    for o in critic.get("obligations",[]):
        if not o.get("mandatory",True):
            continue
        refs=set(o.get("source_refs") or [])
        hit=not refs or bool(refs & covered_refs)
        rows.append({
            "id":o.get("id"),
            "statement":o.get("statement"),
            "source_refs":sorted(refs),
            "covered":hit,
        })
    return {
        "passed":sum(x["covered"] for x in rows),
        "total":len(rows),
        "missing":[x for x in rows if not x["covered"]],
        "rows":rows,
    }
