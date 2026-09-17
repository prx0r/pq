from __future__ import annotations
from typing import Any
from .models import Lane
from .policies import KernelPolicy, FINAL_POLICY

DEFAULT_POLICIES=[
    "policy.direct","policy.reuse_first","policy.test_first",
    "policy.redteam_first","policy.repair_first"
]

def make_lanes(
    contract_root: str,
    *,
    count: int,
    mission_budget_usd: float,
    evaluator_root: str,
    policy: KernelPolicy = FINAL_POLICY,
) -> list[Lane]:
    count=max(1,min(count,len(DEFAULT_POLICIES)))
    if policy.shared_lane_budget:
        exploration=min(mission_budget_usd*0.10,2.0)
    else:
        exploration=mission_budget_usd
    return [
        Lane(
            id=f"lane-{i+1}",
            contract_root=contract_root,
            policy=DEFAULT_POLICIES[i],
            budget={"usd":exploration},
            evaluator_root=evaluator_root,
        )
        for i in range(count)
    ]

def rank_lanes(lanes: list[Lane], *, policy: KernelPolicy = FINAL_POLICY) -> list[Lane]:
    valid=[]
    for lane in lanes:
        if not lane.actuality or not lane.qp_valid or lane.authority_violations:
            continue
        if policy.evaluator_immutable_per_lane:
            expected=lanes[0].evaluator_root if lanes else None
            if lane.evaluator_root != expected:
                continue
        valid.append(lane)
    def key(x: Lane):
        m=x.metrics
        return (
            float(m.get("human_minutes",0)),
            float(m.get("cost_usd",0)),
            float(m.get("wall_minutes",0)),
            float(m.get("tokens",0)),
            float(m.get("attempts",0)),
            float(m.get("complexity",0)),
        )
    return sorted(valid,key=key)
