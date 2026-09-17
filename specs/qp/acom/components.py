"""Components: typed contracts for everything pluggable
(circuitboard2.md). A component advertises inputs, outputs, cost,
latency, reliability, proof level, side effects — and every number but
the priors is learned from run receipts, never guessed.
"""
import json
import os
import statistics

from .canonical import obj_id

REGISTRY = {}


def register(spec: dict) -> dict:
    """Register a component contract. Required: id, inputs, outputs.
    Version is content-derived: changing the contract changes the id."""
    for k in ("id", "inputs", "outputs"):
        if k not in spec:
            raise ValueError(f"component missing {k}")
    spec = dict(spec)
    spec["version"] = obj_id("comp", {k: v for k, v in spec.items()
                                      if k != "version"})
    spec.setdefault("cost", {"median": 0.0, "p95": 0.0})
    spec.setdefault("latency_ms", {"median": 0, "p95": 0})
    spec.setdefault("reliability", {})
    spec.setdefault("proof_level", 0)
    spec.setdefault("side_effects", [])
    spec.setdefault("deterministic", False)
    spec.setdefault("stats", {})
    REGISTRY[spec["id"]] = spec
    return spec


def get(cid: str) -> dict:
    """Fetch a registered component contract; raises, never returns None."""
    if cid not in REGISTRY:
        raise ValueError(f"unknown component {cid}")
    return REGISTRY[cid]


def list_all():
    """Registered component ids, sorted. Empty registry is valid."""
    return sorted(REGISTRY)


def record_run(cid: str, task_class: str, cost: float, latency_ms: int,
               success: bool, info_gain: float = 0.0):
    """Fold one run receipt into the component's transfer function."""
    spec = get(cid)
    s = spec["stats"].setdefault(task_class, {"n": 0, "costs": [],
                                              "latencies": [], "wins": 0,
                                              "gains": []})
    s["n"] += 1
    s["costs"].append(cost)
    s["latencies"].append(latency_ms)
    s["wins"] += 1 if success else 0
    s["gains"].append(info_gain)
    spec["cost"]["median"] = statistics.median(s["costs"])
    spec["cost"]["p95"] = _p95(s["costs"])
    spec["latency_ms"]["median"] = int(statistics.median(s["latencies"]))
    spec["latency_ms"]["p95"] = int(_p95(s["latencies"]))
    spec["reliability"][task_class] = s["wins"] / s["n"]
    return spec


def _p95(xs):
    if not xs:
        return 0
    ys = sorted(xs)
    return ys[min(len(ys) - 1, int(len(ys) * 0.95))]


def success_prob(cid: str, task_class: str) -> float:
    """Measured win rate, else declared prior, else 0.5. Receipts beat
    priors as soon as any exist."""
    spec = get(cid)
    s = spec["stats"].get(task_class)
    if not s:
        return float(spec["reliability"].get(task_class,
                                             spec["reliability"].get("prior", 0.5)))
    return s["wins"] / s["n"]


def save(path: str):
    """Persist the registry (specs + learned stats) as canonical JSON."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(REGISTRY, open(path, "w"), sort_keys=True, indent=1)


def load(path: str):
    """Restore a saved registry, replacing in-memory state."""
    REGISTRY.clear()
    REGISTRY.update(json.load(open(path)))
