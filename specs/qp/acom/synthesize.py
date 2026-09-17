"""Circuit synthesis + VOI routing (circuitboard2.md, northstar §13).

Routing is optimization, not vibes: enumerate candidate component
circuits, score expected verified outcome value over cost/latency,
subject to proof level. UNKNOWN verdicts route through an explicit
VOI gate before any expensive component fires.
"""
from . import components


def voi_decide(p_changes: float, decision_value: float, reliability: float,
               reuse: float, cost: float, safety: float = 5.0) -> dict:
    """Acquire iff VOI > cost x safety. Buckets, not fake precision."""
    voi = p_changes * decision_value * reliability * reuse
    return {"voi": round(voi, 4), "acquire": voi > cost * safety,
            "threshold": round(cost * safety, 4)}


def candidate_circuits(task_class: str):
    """Template circuits from cheap to expensive. Each is a component
    list; evaluation semantics belong to the caller (gates decide)."""
    return [
        {"id": "cheap-gates",
         "components": ["evidence_local", "killfeed_gate"],
         "proof": 4},
        {"id": "cheap-search-gates",
         "components": ["web_search", "evidence_local", "killfeed_gate"],
         "proof": 4},
        {"id": "paid-data-gates",
         "components": ["web_search", "paid_report", "evidence_local",
                        "killfeed_gate"],
         "proof": 7},
        {"id": "full-eval",
         "components": ["web_search", "paid_report", "monte_carlo",
                        "cg_eval", "killfeed_gate"],
         "proof": 7},
    ]


def _chain_stats(comps, task_class):
    cost = sum(components.get(c)["cost"]["median"] for c in comps)
    lat = sum(components.get(c)["latency_ms"]["median"] for c in comps)
    p = 1.0
    for c in comps:
        p *= components.success_prob(c, task_class)
    proof = max([components.get(c)["proof_level"] for c in comps] + [0])
    return cost, lat, p, proof


def synthesize(task_class: str, value: float, budget: float,
               deadline_ms: int, required_proof: int) -> dict:
    """argmax over circuits of expected value, subject to budgets."""
    best, scored = None, []
    for cand in candidate_circuits(task_class):
        comps = cand["components"]
        try:
            cost, lat, p, proof = _chain_stats(comps, task_class)
        except ValueError:
            continue  # unknown component: not composable, skip
        feasible = (cost <= budget and lat <= deadline_ms
                    and proof >= required_proof)
        ev = p * value - cost
        scored.append({"circuit": cand["id"], "components": comps,
                       "cost": round(cost, 4), "latency_ms": lat,
                       "p_success": round(p, 4), "proof": proof,
                       "expected_value": round(ev, 4),
                       "feasible": feasible})
        if feasible and (best is None or ev > best["expected_value"]):
            best = scored[-1]
    return {"best": best, "candidates": scored}


def ensure_defaults():
    """Seed registry with the thesis's own example chips (priors only;
    receipts overwrite them). Idempotent."""
    if "killfeed_gate" in components.REGISTRY:
        return
    components.register({"id": "evidence_local", "inputs": ["scope"],
                         "outputs": ["evidence"], "proof_level": 2,
                         "deterministic": True,
                         "reliability": {"prior": 0.9}})
    components.register({"id": "killfeed_gate", "inputs": ["evidence"],
                         "outputs": ["TRUE|FALSE|UNKNOWN"], "proof_level": 7,
                         "deterministic": True,
                         "reliability": {"prior": 0.95}})
    components.register({"id": "web_search", "inputs": ["query"],
                         "outputs": ["evidence_candidates"],
                         "cost": {"median": 0.003, "p95": 0.01},
                         "latency_ms": {"median": 2000, "p95": 5000},
                         "proof_level": 1,
                         "reliability": {"prior": 0.7}})
    components.register({"id": "paid_report", "inputs": ["report_id"],
                         "outputs": ["evidence"],
                         "cost": {"median": 1.0, "p95": 1.0},
                         "latency_ms": {"median": 10000, "p95": 30000},
                         "proof_level": 5,
                         "reliability": {"prior": 0.9}})
    components.register({"id": "monte_carlo", "inputs": ["world", "n"],
                         "outputs": ["distribution"],
                         "cost": {"median": 0.05, "p95": 0.1},
                         "latency_ms": {"median": 5000, "p95": 15000},
                         "proof_level": 4,
                         "reliability": {"prior": 0.8}})
    components.register({"id": "cg_eval", "inputs": ["candidate_run",
                                                     "worldpack"],
                         "outputs": ["verified_score", "receipt"],
                         "cost": {"median": 0.40, "p95": 0.56},
                         "latency_ms": {"median": 20000, "p95": 31000},
                         "proof_level": 7,
                         "reliability": {"prior": 0.94}})
