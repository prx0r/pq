"""Grants: explicit cryptographic permission for consequences (§2, §28).

A grant names subject + capability + constraints + predicates + expiry.
Verification is deterministic and local: expiry, predicate satisfaction
against a supplied fact map, and constraint arithmetic. Signatures are
carried opaquely in v0 ( ed25519 verify lands with the authority layer;
until then an UNSIGNED grant never authorizes — fail closed).
"""

import operator

_OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt,
        ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _predicate_holds(pred: str, facts: dict) -> bool:
    """Tiny predicate language: `<dotted.key> <op> <literal>`."""
    parts = pred.split()
    if len(parts) != 3:
        return False
    key, op, lit = parts
    if op not in _OPS:
        return False
    cur = facts
    for bit in key.split("."):
        if not isinstance(cur, dict) or bit not in cur:
            return False
        cur = cur[bit]
    try:
        want = float(lit)
        got = float(cur)
    except (TypeError, ValueError):
        want, got = lit.strip("'\""), str(cur)
    return bool(_OPS[op](got, want))


def verify_grant(grant: dict, action: dict, facts: dict,
                 now_iso: str) -> dict:
    """Decide whether `action` is authorized. Returns {ok, reason}."""
    if grant.get("expiry", "") < now_iso:
        return {"ok": False, "reason": "grant expired"}
    if action.get("capability") != grant.get("capability"):
        return {"ok": False, "reason": "capability mismatch"}
    for k in (grant.get("constraints") or {}):
        if k not in ("max_value", "calls", "max_calls", "asset",
                     "max_risk_usd"):
            return {"ok": False, "reason": f"unknown constraint {k}"}
    for k, v in (grant.get("constraints") or {}).items():
        if k in ("max_value", "calls", "max_calls", "max_risk_usd"):
            field = {"max_value": "value", "calls": "calls",
                     "max_calls": "calls", "max_risk_usd": "risk_usd"}[k]
            have = action.get(field, 0)
            try:
                if float(have) > float(v):
                    return {"ok": False,
                            "reason": f"constraint {k} exceeded"}
            except (TypeError, ValueError):
                return {"ok": False, "reason": f"bad constraint {k}"}
        elif k == "asset" and action.get("asset") != v:
            return {"ok": False, "reason": "asset mismatch"}
    for pred in grant.get("predicates", []):
        if not _predicate_holds(pred, facts):
            return {"ok": False, "reason": f"predicate failed: {pred}"}
    if not grant.get("signature"):
        return {"ok": False, "reason": "unsigned grant (fail closed)"}
    if _looks_pubkey(grant.get("subject", "")):
        from . import crypto as _crypto
        if not _crypto.verify_grant_sig(grant["subject"], grant,
                                        grant["signature"]):
            return {"ok": False, "reason": "bad grant signature"}
    return {"ok": True, "reason": "grant authorizes action"}


def _looks_pubkey(s: str) -> bool:
    return (isinstance(s, str) and len(s) == 64
            and all(c in "0123456789abcdef" for c in s.lower()))
