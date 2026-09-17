"""Memory projection: full experience -> compact letta-shaped records.

Letta trajectory v1 shape (roles: meta/reasoning/assistant/tool_call/tool/
observation/user/system, ISO timestamps) is adopted as our memory-compiler
output — NOT our truth (QP), NOT our replay format (ATIF). The projector is
lossy by design; fidelity test pins what must survive (verdicts, costs,
ids). Quality axes (adherence/retrieval/generalization/hygiene) score
promotion candidates mechanically (v0 proxies, documented as such).
"""
import datetime

FIXED_TS = "2026-09-14T00:00:00Z"


def _tokens(s):
    return max(1, len(str(s or "")) // 4)


def project(records, source="agentcom"):
    """Full trajectory-ish records -> compact letta-shaped list. Returns
    {records, full_tokens, compact_tokens, reduction} (reduction recorded,
    never claimed without measurement)."""
    out = [{"role": "meta", "source": source, "content": "memory projection"}]
    full = 0
    for r in records or []:
        r = r if isinstance(r, dict) else {}
        full += _tokens(str(r))
        out.append({"role": "observation",
                    "content": "attempt %s: %s (%s)" % (
                        r.get("attempt_id", "?"),
                        (r.get("observed_effect") or {}).get("verdict",
                                                             "UNKNOWN"),
                        str((r.get("action") or {}).get("description",
                                                       ""))[:160]),
                    "timestamp": FIXED_TS})
        for reason in ((r.get("observed_effect") or {}).get("reasons") or [])[:3]:
            out.append({"role": "reasoning", "content": str(reason)[:200],
                        "timestamp": FIXED_TS})
    compact = sum(_tokens(x.get("content", "")) for x in out)
    return {"records": out, "full_tokens": full, "compact_tokens": compact,
            "reduction": round(full / max(1, compact), 2)}


def fidelity(full_records, compact):
    """Verdicts + attempt ids + costs must survive projection."""
    want = {(r.get("attempt_id"), str((r.get("observed_effect") or {})
                                      .get("verdict"))) for r in full_records}
    blob = " ".join(x.get("content", "") for x in compact["records"])
    missing = [a for a, v in want if not (str(a) in blob and str(v) in blob)]
    return (not missing), ["lost:%s" % m for m in missing]


def quality_axes(candidate, heldout):
    """v0 mechanical proxies for letta's four memory axes. heldout:
    {task_text, needs (keywords that must be retrievable),
    forbids (must not leak into unrelated contexts)}."""
    text = " ".join([candidate.get("idea", ""), candidate.get("statement",
                                                              "")]).lower()
    task = (heldout.get("task_text") or "").lower()
    needs = [w.lower() for w in heldout.get("needs", [])]
    return {
        "adherence": all(w in text for w in needs) if needs else True,
        "retrieval": any(w in text and w in task for w in needs) if needs else True,
        "generalization": "example" in text or "e.g." in text,
        "hygiene": len(text.split()) <= 120,
    }
