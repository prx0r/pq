from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .canonical import full_id

@dataclass
class Trajectory:
    id: str
    contract_root: str
    lane_id: str
    proof_ids: list[str]
    route_ids: list[str]
    failures: list[str]
    metrics: dict[str, Any]
    verified: bool

def bank_trajectory(
    *,
    contract_root: str,
    lane_id: str,
    proof_ids: list[str],
    route_ids: list[str],
    failures: list[str],
    metrics: dict[str, Any],
    verified: bool,
) -> Trajectory:
    body={
        "contract_root":contract_root,
        "lane_id":lane_id,
        "proof_ids":proof_ids,
        "route_ids":route_ids,
        "failures":failures,
        "metrics":metrics,
        "verified":verified,
    }
    return Trajectory(id=full_id("trajectory",body),**body)

def compare(run1: Trajectory, run2: Trajectory) -> dict[str, Any]:
    same=run1.contract_root==run2.contract_root
    hard=run1.verified and run2.verified and same
    objective=("human_minutes","cost_usd","wall_minutes","tokens","attempts","complexity")
    a=tuple(float(run1.metrics.get(k,0)) for k in objective)
    b=tuple(float(run2.metrics.get(k,0)) for k in objective)
    return {
        "same_contract":same,
        "both_verified":run1.verified and run2.verified,
        "improved":hard and b<a,
        "run1_vector":a,
        "run2_vector":b,
    }
