"""Decision log + calibration store for the 0–9 human rail.

Every answered H-task banks a HumanDecision: task id, the prediction as it
stood *before display* (server-side, never client-supplied), the actual
press, timestamp, and context hash. Calibration is the rolling match rate
of prediction vs actual — the signal the autonomy ladder reads.

Provenance: digit semantics ported from specs/human/hloop/model.py
DEFAULT_ACTIONS; the banked-prediction rule mirrors its controller's
PREDICTION_BEFORE_HUMAN enforcement. Stdlib only.
"""
from __future__ import annotations

import json
import os
import time

# Ported from specs/human/hloop/model.py DEFAULT_ACTIONS (stable macro map).
ACTION_LABELS = {
    "0": "ABSTAIN_OR_NEED_CONTEXT",
    "1": "REJECT",
    "2": "DEFER",
    "3": "REPLAN",
    "4": "CHEAPER_ROUTE",
    "5": "CONTINUE",
    "6": "APPROVE_ONCE",
    "7": "APPROVE_BOUNDED",
    "8": "PROMOTE_PREFERRED_ROUTE",
    "9": "MAX_AUTONOMY_WITHIN_GRANT",
}


def semantic_action(value: str) -> str:
    """Digit press → macro label. Non-digit values pass through as-is."""
    return ACTION_LABELS.get(str(value).strip(), str(value)[:60])


def log_decision(log_path: str, task, actual: str,
                 via: str = "dashboard") -> dict:
    """Bank one HumanDecision and append it to the JSONL log."""
    prediction = task.prediction  # banked at emit, before any display
    entry = {"ts": int(time.time()), "task_id": task.task_id,
             "kind": task.kind, "question": task.question,
             "prediction_before_display": prediction,
             "confidence": task.confidence, "actual": actual,
             "hit": bool(prediction) and prediction == actual,
             "semantic_action": semantic_action(actual),
             "context_hash": task.context_hash,
             "campaign": task.campaign, "lane": task.lane, "via": via}
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _iter_decisions(log_path: str):
    if not os.path.exists(log_path):
        return
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def calibration(log_path: str, window: int = 20) -> dict:
    """Rolling calibration over banked decisions.

    Only digit tasks with a non-empty banked prediction score; confirms and
    unpredicted tasks are counted but never scored.
    """
    total = hits = 0
    recent: list[dict] = []
    by_kind: dict[str, dict] = {}
    for e in _iter_decisions(log_path):
        if e.get("type") == "summary":
            continue
        k = e.get("kind", "")
        b = by_kind.setdefault(k, {"decisions": 0, "hits": 0})
        b["decisions"] += 1
        if k == "digit" and e.get("prediction_before_display"):
            total += 1
            recent.append(e)
            if e.get("hit"):
                hits += 1
                b["hits"] += 1
    last = recent[-window:]
    last_hits = sum(1 for e in last if e.get("hit"))
    return {"decisions": sum(b["decisions"] for b in by_kind.values()),
            "scored": total, "hits": hits,
            "rate": round(hits / total, 3) if total else 0.0,
            f"last{window}": {"scored": len(last),
                              "rate": round(last_hits / len(last), 3)
                              if last else 0.0},
            "by_kind": by_kind}
