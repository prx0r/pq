"""Trajectory bank: duality enforced at file time (gitplans P11),
vocabulary enforced by level (test2.md Rule 1).

Filing a trajectory writes THREE views atomically: full record, ATIF
replay, compact memory projection. The fidelity gate refuses the whole
filing if the compact view loses verdicts/costs/ids. Tier routing:
L0* -> observations/, L1* -> verified/, L2+ -> candidates/, L5 needs a
promotion receipt or it is refused. L0 can NEVER file under verified/
facts/promoted — attempted misfiling raises TierRefused.
"""
import json
import os

from trajectory import atif, memory


class FidelityRefused(ValueError):
    pass


class TierRefused(ValueError):
    pass


def tier_for(level):
    """Level -> store tier. Unknown levels refuse (fail closed)."""
    level = str(level or "")
    if level.startswith("L0"):
        return "observations"
    if level.startswith("L1"):
        return "verified"
    if level.startswith(("L2", "L3", "L4")):
        return "candidates"
    if level.startswith("L5"):
        return "promoted"
    raise TierRefused("unknown-level:%s" % (level,))


def file_trajectory(root, traj, agent=None, session_id=""):
    """Returns {dir, files, tier}. Raises FidelityRefused on projection
    loss. Routes by level; L0 lands in observations/, never verified/."""
    return file_at(root, traj, tier_for(traj.get("level", "")), agent,
                   session_id)


def file_at(root, traj, tier, agent=None, session_id=""):
    """Explicit-tier filing. Refuses level/tier mismatch and L5 without a
    promotion receipt. The tier recorded in the index is the tier written."""
    level = str(traj.get("level", ""))
    want = tier_for(level)
    if tier != want:
        raise TierRefused("level %s belongs in %s, not %s"
                          % (level, want, tier))
    if tier == "promoted" and not traj.get("promotion_receipt"):
        raise TierRefused("promoted needs promotion_receipt")
    compact = memory.project(traj.get("attempts", []),
                             source="bank")
    ok, missing = memory.fidelity(traj.get("attempts", []), compact)
    if not ok:
        raise FidelityRefused("; ".join(missing))
    tid = "".join(c for c in str(traj.get("trajectory_id", "t"))
                  if c.isalnum() or c in "-_:") or "t"
    d = os.path.join(root, tier, tid)
    os.makedirs(d, exist_ok=True)
    full_p = os.path.join(d, "trajectory.json")
    atif_p = os.path.join(d, "trajectory.atif.json")
    mem_p = os.path.join(d, "trajectory.memory.json")
    with open(full_p, "w") as fh:
        json.dump(traj, fh, indent=2, sort_keys=True)
    with open(atif_p, "w") as fh:
        json.dump(atif.from_trajectory(traj, agent, session_id), fh,
                  indent=2, sort_keys=True)
    with open(mem_p, "w") as fh:
        json.dump(compact, fh, indent=2, sort_keys=True)
    with open(os.path.join(root, "index.jsonl"), "a") as fh:
        fh.write(json.dumps({"trajectory_id": traj.get("trajectory_id"),
                             "policy": traj.get("policy_id"),
                             "level": traj.get("level"),
                             "tier": tier,
                             "reduction": compact["reduction"],
                             "dir": d}, sort_keys=True) + "\n")
    return {"dir": d, "files": [full_p, atif_p, mem_p], "tier": tier}
