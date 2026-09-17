"""Versioned deterministic components (circuitboard2 extension).

Every component version is content-hashed and chained: v2 names the v1
it supersedes, and no version is ever edited in place. Each version
carries its COMPLETE history — every run linked by receipt id, with
model, latency, cost, outcome, and outputs root. Determinism is
mechanical: same version + same canonical inputs = byte-identical
outputs, verified by replay, not claimed in prose.

Nothing here spends, calls network, or touches keys. Pure bookkeeping
over run records the caller supplies or the execute() wrapper makes.
"""
from .canonical import obj_id
from .components import REGISTRY, get

_VERSIONS = {}


def _snapshot(spec: dict) -> dict:
    import copy
    return copy.deepcopy(spec)


def revise(cid: str, changes: dict, reason: str = "") -> dict:
    """New version superseding cid. Old version is untouched (queryable
    forever); the chain is what promotion compares."""
    from . import components as _c
    old = get(cid)
    _VERSIONS[old["version"]] = _snapshot(old)
    spec = {k: v for k, v in old.items()
            if k not in ("version", "stats", "history", "runs")}
    spec.update(changes)
    spec["supersedes"] = old["version"]
    spec["revision_reason"] = reason
    return _c.register(spec)


def _resolve(cid: str) -> dict:
    """Specs by id (latest) or by content version (any generation)."""
    if cid in REGISTRY:
        return REGISTRY[cid]
    if cid in _VERSIONS:
        return _VERSIONS[cid]
    for spec in REGISTRY.values():
        if spec.get("version") == cid:
            return spec
    raise ValueError(f"unknown component {cid}")


def chain(cid: str) -> list:
    """Oldest-first version chain ending at cid (by id or version)."""
    cur = _resolve(cid)
    out, seen = [], set()
    while cur is not None and cur["version"] not in seen:
        seen.add(cur["version"])
        out.append(cur)
        nxt = cur.get("supersedes")
        cur = _VERSIONS.get(nxt) if nxt else None
    return list(reversed(out))


def save_all(path: str):
    """Persist registry + version archive (history survives restarts)."""
    import json
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump({"registry": REGISTRY, "archive": _VERSIONS},
              open(path, "w"), sort_keys=True, indent=1)


def load_all(path: str):
    """Restore registry + archive."""
    import json
    d = json.load(open(path))
    REGISTRY.clear()
    REGISTRY.update(d["registry"])
    _VERSIONS.clear()
    _VERSIONS.update(d.get("archive", {}))


def attach_run(cid: str, task_class: str, run: dict):
    """Attach a full run record to a version's history. Required keys:
    receipt_id, model, latency_ms, cost, success. Optional: outputs_root,
    info_gain, note. Totals derive from history — never stored twice."""
    from . import components as _c
    spec = get(cid)
    for k in ("receipt_id", "model", "latency_ms", "cost", "success"):
        if k not in run:
            raise ValueError(f"run record missing {k}")
    hist = spec.setdefault("history", {}).setdefault(task_class, [])
    if any(h["receipt_id"] == run["receipt_id"] for h in hist):
        raise ValueError("duplicate receipt_id (replay, not a new run)")
    hist.append(dict(run))
    _c.record_run(cid, task_class, float(run["cost"]),
                  int(run["latency_ms"]), bool(run["success"]),
                  float(run.get("info_gain", 0.0)))
    return spec


def totals(cid: str, task_class: str = "") -> dict:
    """Derived totals for one VERSION (id resolves to latest).
    Computed from history every call — a total that disagrees with its
    log is impossible by construction."""
    spec = _resolve(cid)
    classes = [task_class] if task_class else list(
        spec.get("history", {}))
    classes = [task_class] if task_class else list(
        spec.get("history", {}))
    out = {"runs": 0, "wins": 0, "total_cost": 0.0, "total_ms": 0,
           "models": {}, "receipts": []}
    for tc in classes:
        for h in spec.get("history", {}).get(tc, []):
            out["runs"] += 1
            out["wins"] += 1 if h["success"] else 0
            out["total_cost"] = round(out["total_cost"] + float(h["cost"]), 6)
            out["total_ms"] += int(h["latency_ms"])
            m = out["models"].setdefault(h["model"], {"runs": 0, "wins": 0})
            m["runs"] += 1
            m["wins"] += 1 if h["success"] else 0
            out["receipts"].append(h["receipt_id"])
    return out


def compare(old_id: str, new_id: str, task_class: str) -> dict:
    """Promotion evidence: same task class, both versions, deltas.
    Positive cost/latency delta favors new; success delta decides."""
    a, b = totals(old_id, task_class), totals(new_id, task_class)
    if not a["runs"] or not b["runs"]:
        return {"ok": False,
                "reason": "both versions need run history to compare"}
    sa, sb = a["wins"] / a["runs"], b["wins"] / b["runs"]
    return {"ok": True, "old_runs": a["runs"], "new_runs": b["runs"],
            "success_delta": round(sb - sa, 4),
            "cost_delta": round(b["total_cost"] - a["total_cost"], 6),
            "time_delta_ms": b["total_ms"] - a["total_ms"],
            "promote": sb > sa}


def execute(cid: str, task_class: str, inputs: dict, model: str,
            handler, cost: float = 0.0) -> dict:
    """Deterministic execution wrapper. Handler MUST be pure on canonical
    inputs. Runs twice on first call per (version, inputs) and refuses to
    record unless both bytes match — determinism verified, not assumed.
    Returns {outputs, receipt_id, latency_ms} and attaches the run."""
    import time
    from .canonical import canonical, sha256_hex
    from . import runs as _runs
    key = sha256_hex(canonical({"v": get(cid)["version"], "in": inputs}))
    t0 = time.monotonic_ns()
    o1 = handler(dict(inputs))
    o2 = handler(dict(inputs))
    ms = int((time.monotonic_ns() - t0) / 1e6)
    if canonical(o1) != canonical(o2):
        raise ValueError("nondeterministic handler: outputs differ")
    rec = _runs.build({"id": f"task:{task_class}"}, model, key,
                      [{"handler": get(cid)["version"]}], [inputs], [o1],
                      cost, [{"t": "execute"}])
    attach_run(cid, task_class,
               {"receipt_id": rec["id"], "model": model, "latency_ms": ms,
                "cost": cost, "success": True, "outputs_root": rec["outputs_root"]})
    return {"outputs": o1, "receipt_id": rec["id"], "latency_ms": ms}
