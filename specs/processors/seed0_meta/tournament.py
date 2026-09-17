from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import hashlib, json, random

def _hash(tag,x):
    raw=json.dumps(x,sort_keys=True,separators=(",",":"))
    return "sha256:"+hashlib.sha256(f"{tag}\0{raw}".encode()).hexdigest()

@dataclass
class LanePolicy:
    id: str
    contract_root: str
    evaluator_root: str
    processor_graph: list[str]
    model: str
    reasoning_effort: str
    budget: dict[str,Any]
    mutation: dict[str,Any]
    foundation_run_id: str | None = None
    execution_mode: str = "SHADOW_WORLD"

@dataclass
class LaneResult:
    lane_id: str
    contract_root: str
    evaluator_root: str
    qp_valid: bool
    actuality: bool
    authority_violations: int
    metrics: dict[str,Any]
    processor_graph: list[str]
    proof_ids: list[str]=field(default_factory=list)
    artifacts: list[str]=field(default_factory=list)

def generate_five_lanes(
    *,
    contract_root: str,
    evaluator_root: str,
    base_graph: list[str],
    mission_budget_usd: float,
    model: str="driver/default",
    foundation_run_id: str | None=None,
    seed: int=20260914,
) -> list[LanePolicy]:
    rng=random.Random(seed)
    # Four exploitation-biased policies + one mandatory exploration lane.
    profiles=[
        ("direct","medium",{"strategy":"direct"}),
        ("reuse_first","low",{"strategy":"reuse_first"}),
        ("test_first","medium",{"strategy":"test_first"}),
        ("redteam_first","high",{"strategy":"redteam_first"}),
        ("explore_mutation","high",{"strategy":"explore","mutation_axis":"processor_graph"}),
    ]
    lane_cap=min(2.0,max(0.0,mission_budget_usd*0.10))
    out=[]
    for idx,(name,effort,mut) in enumerate(profiles,1):
        graph=list(base_graph)
        if name=="direct":
            # Direct lane intentionally avoids history/reuse front-loading so the
            # tournament measures whether those processors actually add value.
            graph=[x for x in graph if x not in {"history.retrieve","reuse.search"}]
        elif name=="reuse_first":
            graph=[x for x in graph if x not in {"history.retrieve","reuse.search"}]
            graph=["history.retrieve","reuse.search"]+graph
        elif name=="test_first" and "code.test" in graph:
            graph=["code.test"]+[x for x in graph if x!="code.test"]
        elif name=="redteam_first":
            graph=["redteam.falsify"]+graph
        elif name=="explore_mutation":
            # Exploration must not be identical to the foundation.
            candidates=[
                "problem.decompose","cg.simulate","probe.design",
                "tool.discover","data.discover"
            ]
            extra=rng.choice([x for x in candidates if x not in graph] or candidates)
            insert_at=rng.randrange(0,len(graph)+1)
            graph.insert(insert_at,extra)

        out.append(LanePolicy(
            id=f"lane-{idx}-{name}",
            contract_root=contract_root,
            evaluator_root=evaluator_root,
            processor_graph=graph,
            model=model,
            reasoning_effort=effort,
            budget={"usd":lane_cap},
            mutation=mut,
            foundation_run_id=foundation_run_id,
        ))
    return out

def rank(results: list[LaneResult]) -> list[LaneResult]:
    if not results:
        return []
    contract=results[0].contract_root
    evaluator=results[0].evaluator_root
    valid=[
        r for r in results
        if r.contract_root==contract
        and r.evaluator_root==evaluator
        and r.qp_valid
        and r.actuality
        and r.authority_violations==0
    ]
    def key(r):
        m=r.metrics
        return (
            float(m.get("human_minutes",0)),
            float(m.get("cost_usd",0)),
            float(m.get("wall_seconds",0)),
            float(m.get("tokens",0)),
            float(m.get("attempts",0)),
            float(m.get("complexity",0)),
        )
    return sorted(valid,key=key)

def tournament_receipt(results: list[LaneResult]) -> dict[str,Any]:
    ordered=rank(results)
    body={
        "contract_root":results[0].contract_root if results else None,
        "evaluator_root":results[0].evaluator_root if results else None,
        "participants":[asdict(r) for r in results],
        "ranked":[r.lane_id for r in ordered],
        "winner":ordered[0].lane_id if ordered else None,
    }
    return {**body,"receipt_id":_hash("seed0/tournament",body)}


def promote_live_lane(lanes: list[LanePolicy], winner_id: str) -> list[LanePolicy]:
    """Return a new lane list with exactly one LIVE lane.

    Shadow tournaments may freely compare full-task policies in replayable /
    isolated worlds. Only the selected winner crosses the real consequence belt.
    """
    from dataclasses import replace
    if winner_id not in {x.id for x in lanes}:
        raise ValueError("winner not in lanes")
    return [
        replace(x, execution_mode="LIVE" if x.id==winner_id else "SHADOW_WORLD")
        for x in lanes
    ]
