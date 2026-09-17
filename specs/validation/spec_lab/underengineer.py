from __future__ import annotations
from typing import Any
from .models import ActualityContract, ATask
from .policies import KernelPolicy, FINAL_POLICY
from .validation import reject_orphan_tasks

KIND_BIAS = {
    "ALREADY_TRUE": -1000,
    "REUSE": 0,
    "CONFIGURE": 0.25,
    "INTEGRATE": 0.5,
    "BUILD": 3,
    "BUY": 4,
    "BLOCKED": 10,
}

# Structural underengineering order. Cost/time estimates proposed by an LLM
# are heuristic and must not by themselves cause a leap from a reusable primitive
# to a bespoke build or purchase.
KIND_RANK = {
    "ALREADY_TRUE": -1,
    "REUSE": 0,
    "CONFIGURE": 1,
    "INTEGRATE": 2,
    "BUILD": 3,
    "BUY": 4,
    "BLOCKED": 5,
}

def route_score(route: dict[str, Any], *, reuse_first: bool = True) -> float:
    kind = route.get("kind", "BUILD")
    bias = KIND_BIAS.get(kind, 5) if reuse_first else 0
    return (
        bias
        + float(route.get("cost_usd") or 0)
        + 0.01 * float(route.get("time_minutes") or 0)
        + 0.5 * float(route.get("human_minutes") or 0)
        + 2.0 * float(route.get("irreversibility") or 0)
        + 0.2 * float(route.get("complexity") or 0)
        - 0.05 * float(route.get("information_gain") or 0)
    )

def choose_route(
    routes: list[dict[str, Any]],
    *,
    machine_capabilities: set[str],
    human_capabilities: set[str],
    policy: KernelPolicy,
    allow_already_true: bool = False,
) -> dict[str, Any] | None:
    candidates=[]
    for route in routes:
        # `admissible` is a model proposal, not authority. Runtime route
        # verification may later attach `runtime_admissible=False`; only that
        # trusted fact may eliminate a candidate here.
        if route.get("runtime_admissible") is False:
            continue
        if route.get("kind") == "ALREADY_TRUE" and not allow_already_true:
            continue
        required=set(route.get("capabilities") or [])
        if route.get("kind") == "BLOCKED":
            # Human-only route may be selected only as an explicit block candidate.
            if required and not required.issubset(human_capabilities | machine_capabilities):
                continue
        elif required and not required.issubset(machine_capabilities):
            continue
        candidates.append(route)
    if not candidates:
        # Preserve blocked/human routes as evidence for escalation if no machine route.
        blocked=[r for r in routes if r.get("kind")=="BLOCKED" and r.get("runtime_admissible") is not False]
        if blocked:
            return min(blocked,key=lambda r:route_score(r,reuse_first=policy.reuse_first))
        return None
    if policy.reuse_first:
        return min(candidates,key=lambda r:(
            KIND_RANK.get(r.get("kind","BUILD"),99),
            route_score(r,reuse_first=False),
            str(r.get("id","")),
        ))
    return min(candidates,key=lambda r:route_score(r,reuse_first=False))

def build_minimal_plan(
    contract: ActualityContract,
    *,
    machine_capabilities: set[str] | None = None,
    human_capabilities: set[str] | None = None,
    policy: KernelPolicy = FINAL_POLICY,
) -> list[ATask]:
    machine_capabilities = machine_capabilities or set()
    human_capabilities = human_capabilities or set()
    tasks=[]
    for claim in contract.claims:
        if claim.kind != "leaf" or not claim.mandatory:
            continue
        if policy.stop_when_actuality_true and claim.state == "TRUE":
            continue
        route = choose_route(
            claim.routes,
            machine_capabilities=machine_capabilities,
            human_capabilities=human_capabilities,
            policy=policy,
            allow_already_true=(claim.state == "TRUE"),
        )
        if route is None:
            route={"id":"no-route","kind":"BLOCKED","cost_usd":0,"time_minutes":0}
        if route.get("kind") == "ALREADY_TRUE":
            continue
        cost = route.get("cost_usd")
        if cost is None and policy.unknown_cost_is_unknown:
            cost_value = None
        else:
            cost_value = float(cost or 0)
        task=ATask(
            id=f"a:{claim.id}",
            covers=[claim.id],
            objective=f"Make {claim.id} contractually TRUE",
            route_id=route.get("id","route"),
            state="BLOCKED_CLAIMED" if route.get("kind")=="BLOCKED" else "READY",
            budget={
                "usd": min(2.0, cost_value if cost_value is not None else 2.0),
                "wall_minutes": min(60, max(5, float(route.get("time_minutes") or 5) * 2)),
            },
            capabilities=list(route.get("capabilities") or []),
            cost_usd=cost_value,
            wall_minutes=route.get("time_minutes"),
            human_minutes=route.get("human_minutes"),
            irreversibility=float(route.get("irreversibility") or 0),
            complexity=float(route.get("complexity") or 0),
            information_gain=float(route.get("information_gain") or 1),
            criticality=3.0 if claim.id in {
                "leaf.xmr_settlement","leaf.merchant_entitlement","leaf.deploy_journey",
                "leaf.domain","leaf.github_merge"
            } else 1.0,
        )
        # Store route kind in a regular capability-neutral field via budget metadata.
        task.budget["route_kind"] = route.get("kind")
        tasks.append(task)
    reject_orphan_tasks(tasks, contract)
    return tasks

def task_priority(task: ATask) -> float:
    numerator = (
        task.expected_actuality_delta
        * task.criticality
        * task.information_gain
    )
    denom = (
        1
        + float(task.cost_usd or 0)
        + float(task.human_minutes or 0)
        + task.irreversibility
        + task.complexity
    )
    return numerator / denom

def ordered(tasks: list[ATask]) -> list[ATask]:
    return sorted(tasks, key=task_priority, reverse=True)
