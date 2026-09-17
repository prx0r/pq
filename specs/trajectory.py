"""Trajectory object + L0-L5 learning ladder (devplan §15/§16).

Every run normalizes to one Trajectory. Ladder transitions require refs:
L1 needs a QP receipt ref, L2 needs >=2 runs, L4 needs a replay ref, L5
needs a promotion receipt. Nothing self-promotes — advance() refuses
without the refs, loudly.
"""
from core import ids

LEVELS = ("L0-observation", "L1-fact", "L2-pattern", "L3-candidate",
          "L4-replay-proven", "L5-promoted")


def build(contract_root, plan_root, policy_id, attempts, actuality_before,
          actuality_after, qp_receipts=None, cost=None, problem_class="",
          model="", components=None, economic_outcome=None):
    t = {"contract_root": contract_root, "plan_root": plan_root,
         "problem_class": problem_class, "policy_id": policy_id,
         "model": model, "components": components or [], "attempts": attempts,
         "actuality_before": actuality_before,
         "actuality_after": actuality_after,
         "qp_receipts": qp_receipts or [], "economic_outcome": economic_outcome,
         "cost": cost or {"tokens": None, "wall_ms": None, "usd": None,
                          "human_minutes": None},
         "level": "L0-observation"}
    t["trajectory_id"] = ids.obj_id("trajectory", {k: v for k, v in t.items()
                                                   if k != "trajectory_id"})
    return t


def advance(trajectory, evidence=None):
    """Attempt one ladder rung. evidence: {qp_receipt?, runs?, replay?,
    promotion?}. Returns (trajectory-or-same, ok, reason)."""
    evidence = evidence or {}
    level = trajectory.get("level", "L0-observation")
    nxt = {"L0-observation": ("L1-fact", "qp_receipt"),
           "L1-fact": ("L2-pattern", "runs"),
           "L2-pattern": ("L3-candidate", None),
           "L3-candidate": ("L4-replay-proven", "replay"),
           "L4-replay-proven": ("L5-promoted", "promotion")}
    if level not in nxt:
        return trajectory, False, "terminal"
    target, need = nxt[level]
    if need == "runs" and len(evidence.get("runs", [])) < 2:
        return trajectory, False, "needs-2-runs"
    if need and need != "runs" and not evidence.get(need):
        return trajectory, False, "needs:%s" % need
    t = dict(trajectory)
    t["level"] = target
    t["trajectory_id"] = ids.obj_id("trajectory", {k: v for k, v in t.items()
                                                   if k != "trajectory_id"})
    return t, True, target
