"""Scheduler-grade priority (devplan §8). Fresh implementation.

Priority(t) = P(dActuality)*B*IG*SV / (1+C+H+I). The agent's 1-5 impact is
one WEAK feature (weight 0.2 on the 0-1 scale), never the score — repeated
enthusiasm cannot move the scheduler. Initially estimated; eventually
learned from Seed0 trajectories (fields below mirror the trajectory cost
record so learning can bind directly).
"""
from loop import compile as _loop


def priority(task):
    t = dict(task or {})
    if t.get("expected_progress") is None:
        base, inputs = _loop.priority(t)
        inputs["impact_weight"] = 0.2
        return round(base * 0.2, 6), inputs
    return _loop.priority(t)


def rank(tasks):
    out = []
    for t in tasks or []:
        t = dict(t)
        score, inputs = priority(t)
        t["priority_score"] = score
        t["priority_inputs"] = inputs
        out.append(t)
    out.sort(key=lambda e: (-e["priority_score"], e.get("task") or ""))
    return out
