"""Recursive a-com modules (circuitboard2.md): boards containing boards.

A module declares inputs/outputs/components/constraints/acceptance in
YAML. Instantiation checks the budget envelope and acceptance proof
level against the measured registry; nesting is just components that
are themselves module ids. Same interface philosophy at every scale:
GT(a,b) … KILLFEED_GAP() … SCARCITY_TRADE() … AUTONOMOUS_TRADE_RESEARCHER.
"""
import os

import yaml

from . import components


def load(path: str) -> dict:
    """Load an a-com module YAML. Missing interface keys fail here, not
    at runtime halfway through a budget."""
    with open(path) as f:
        m = yaml.safe_load(f)
    for k in ("id", "inputs", "outputs", "components", "constraints",
              "acceptance"):
        if k not in m.get("acom", {}):
            raise ValueError(f"module missing acom.{k}")
    return m


def check(mod: dict, task_class: str = "trade_eval") -> dict:
    """Verify a module against measured component stats. Returns a
    verdict dict; a module that cannot meet its envelope fails HERE,
    not at runtime."""
    a = mod["acom"]
    total_cost = 0.0
    total_lat = 0
    min_proof = 999
    missing = []
    for c in a["components"]:
        cid = c["id"] if isinstance(c, dict) else c
        try:
            spec = components.get(cid)
        except ValueError:
            if isinstance(c, dict) and "module" in c:
                continue  # nested board, checked on expansion
            missing.append(cid)
            continue
        total_cost += spec["cost"]["median"]
        total_lat += spec["latency_ms"]["median"]
        min_proof = min(min_proof, spec["proof_level"])
    cons = a["constraints"]
    ok = (not missing
          and total_cost <= cons.get("max_cost", float("inf"))
          and total_lat <= _ms(cons.get("max_latency", "inf"))
          and min_proof >= a["acceptance"].get("proof_level", 0))
    return {"ok": ok, "missing": missing, "cost": round(total_cost, 4),
            "latency_ms": total_lat, "proof": None if min_proof == 999 else min_proof}


def _ms(v) -> float:
    if v == "inf" or v is None:
        return float("inf")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if s.endswith("ms"):
        return float(s[:-2])
    if s.endswith("s"):
        return float(s[:-1]) * 1000
    if s.endswith("m"):
        return float(s[:-1]) * 60000
    raise ValueError(f"bad latency: {v!r}")


def seed_model_chips():
    """LLMs, humans, and coprocessors as ordinary chips (priors only)."""
    if "llm_mimo" in components.REGISTRY:
        return
    for spec in [
        {"id": "llm_mimo", "inputs": ["prompt"], "outputs": ["text"],
         "cost": {"median": 0.002, "p95": 0.01},
         "latency_ms": {"median": 3000, "p95": 12000},
         "proof_level": 1, "reliability": {"prior": 0.6}},
        {"id": "llm_deep", "inputs": ["prompt"], "outputs": ["text"],
         "cost": {"median": 0.02, "p95": 0.08},
         "latency_ms": {"median": 8000, "p95": 30000},
         "proof_level": 1, "reliability": {"prior": 0.75}},
        {"id": "human_oracle", "inputs": ["ambiguous_case"],
         "outputs": ["judgment"],
         "cost": {"median": 3.0, "p95": 5.0},
         "latency_ms": {"median": 900000, "p95": 3600000},
         "proof_level": 3, "reliability": {"prior": 0.99}},
        {"id": "pearl_inference", "inputs": ["prompt"],
         "outputs": ["text", "compute_proof"],
         "cost": {"median": 0.01, "p95": 0.05},
         "latency_ms": {"median": 5000, "p95": 20000},
         "proof_level": 2, "reliability": {"prior": 0.7}},
    ]:
        components.register(spec)


def example_module(path: str):
    """Write the canonical example module (research.killfeed.hbm.v3)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, "w").write(
        "acom:\n"
        "  id: research.killfeed.hbm.v3\n"
        "  inputs: [entity, timestamp]\n"
        "  outputs: [five_predicates, trade_state]\n"
        "  components: [feed_filter, evidence_resolver, paid_data_gate, claim_evaluator]\n"
        "  constraints: {max_cost: 1.00, max_latency: 60s}\n"
        "  acceptance: {proof_level: 7}\n")
