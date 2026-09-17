"""Four-budget scheduler (circuitboard2.md): tokens, seconds, dollars,
EXTERNAL RISK. Risk is budgeted like compute: a grant or plan carries
max_risk_usd, and anything above it refuses before executing.
"""
from . import components


def plan_cost(chain: list, task_class: str = "trade_eval") -> dict:
    """Sum medians AND p95s over a component chain. Both must fit."""
    med = {"tokens": 0, "seconds": 0.0, "dollars": 0.0, "risk": 0.0}
    p95 = {"tokens": 0, "seconds": 0.0, "dollars": 0.0, "risk": 0.0}
    for cid in chain:
        spec = components.get(cid)
        med["dollars"] += spec["cost"]["median"]
        p95["dollars"] += spec["cost"]["p95"]
        med["seconds"] += spec["latency_ms"]["median"] / 1000
        p95["seconds"] += spec["latency_ms"]["p95"] / 1000
        med["risk"] += float(spec.get("risk_usd", {}).get("median", 0.0))
        p95["risk"] += float(spec.get("risk_usd", {}).get("p95", 0.0))
    return {"median": med, "p95": p95}


def fits(chain: list, budgets: dict, task_class: str = "trade_eval",
         use_p95: bool = True) -> dict:
    """True iff the chain fits all four budgets. p95 by default:
    plans must survive variance, not just the median case."""
    est = plan_cost(chain, task_class)["p95" if use_p95 else "median"]
    over = [k for k in ("tokens", "seconds", "dollars", "risk")
            if k in budgets and est[k] > budgets[k]]
    return {"fits": not over, "over": over, "estimate": est}
