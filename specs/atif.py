"""ATIF export: AgentCom trajectories -> Harbor Agent Trajectory Interchange
Format (ATIF-v1 shape, stdlib dicts — no harbor dep).

ATIF owns the full-fidelity replay trace; our envelope (contract/plan/
candidate/policy/receipts/deltas) rides alongside, never inside ATIF
fields. Unknowns stay null. Pure; never raises on malformed input.
"""
ATIF_VERSION = "ATIF-v1.8"


def _step(i, attempt):
    action = (attempt or {}).get("action", {})
    obs = (attempt or {}).get("observed_effect", {})
    cost = (attempt or {}).get("cost", {})
    return {"step_id": i, "timestamp": "2026-09-14T00:00:00Z",
            "source": "agent",
            "message": str(action.get("description", ""))[:2000],
            "reasoning_content": "",
            "tool_calls": [{"tool_call_id": "call-%d" % i,
                            "function_name": str(action.get("kind", "TEST")),
                            "arguments": {}}],
            "observation": {"results": [
                {"source_call_id": "call-%d" % i,
                 "content": str(obs.get("verdict", "UNKNOWN"))}]},
            "metrics": {"prompt_tokens": None, "completion_tokens": None,
                        "cached_tokens": None,
                        "cost_usd": cost.get("usd")}}


def from_trajectory(traj, agent=None, session_id=""):
    """Trajectory dict (our shape) -> ATIF dict."""
    traj = traj or {}
    attempts = traj.get("attempts", [])
    steps = [_step(i, a) for i, a in enumerate(attempts)]
    agent = agent or {}
    total_cost = sum((a.get("cost") or {}).get("usd") or 0 for a in attempts)
    return {"schema_version": ATIF_VERSION,
            "session_id": session_id or traj.get("trajectory_id", ""),
            "agent": {"name": agent.get("name", "agentcom-worker"),
                      "version": agent.get("version", "0.1.0"),
                      "model_name": agent.get("model",
                                              traj.get("model", "unknown"))},
            "steps": steps,
            "final_metrics": {"total_steps": len(steps),
                              "total_cost_usd": round(total_cost, 6),
                              "total_prompt_tokens": None,
                              "total_completion_tokens": None,
                              "total_cached_tokens": None}}


def check_shape(atif):
    """Structural check of our export (not a full ATIF validator)."""
    reasons = []
    if not isinstance(atif, dict):
        return False, ["not-an-object"]
    if not str(atif.get("schema_version", "")).startswith("ATIF-"):
        reasons.append("schema_version")
    if not isinstance(atif.get("steps"), list):
        reasons.append("steps")
    else:
        for i, s in enumerate(atif["steps"]):
            for k in ("step_id", "timestamp", "source"):
                if k not in s:
                    reasons.append("steps[%d].%s" % (i, k))
    for k in ("session_id", "agent", "final_metrics"):
        if k not in atif:
            reasons.append("missing:%s" % k)
    return (not reasons), reasons
