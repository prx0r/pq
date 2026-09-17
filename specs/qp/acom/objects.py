"""The seven canonical objects (northstar §2). Nothing else is primitive.

Every constructor validates its schema and freezes the result: kernel
objects are immutable dicts. Mutation happens only as new events.
"""

from .canonical import obj_id

BOOL3 = ("TRUE", "FALSE", "UNKNOWN")


def _freeze(d: dict) -> dict:
    return dict(d)


def make_state(cursor: int, rules_commit: str, event_root: str,
               state_root: str) -> dict:
    """STATE cursor: replay position + rules + roots. Derived, never stored."""
    assert isinstance(cursor, int) and cursor >= 0
    return _freeze({"kind": "STATE", "cursor": cursor,
                    "rules_commit": rules_commit, "event_root": event_root,
                    "state_root": state_root})


def make_claim(statement: str, domain: str, result: str = "UNKNOWN",
               valid_from: str = "", valid_until: str = "") -> dict:
    """CLAIM with content-derived id: same statement+domain, same id —
    duplicate claims are impossible by construction."""
    assert result in BOOL3, f"bool3 required, got {result!r}"
    assert statement and domain
    c = _freeze({"kind": "CLAIM", "statement": statement, "domain": domain,
                 "result": result, "valid_from": valid_from,
                 "valid_until": valid_until})
    c["id"] = obj_id("claim", {k: v for k, v in c.items() if k != "id"})
    return c


def make_evidence(metric: str, value, unit: str, as_of: str,
                  source: dict) -> dict:
    """EVIDENCE: immutable typed observation. Carries no verdict — verdicts
    live in CLAIMs via gates, never in evidence rows."""
    assert metric and unit and as_of and isinstance(source, dict)
    e = _freeze({"kind": "EVIDENCE", "metric": metric, "value": value,
                 "unit": unit, "as_of": as_of, "source": source})
    e["id"] = "sha256:" + obj_id("ev", {k: v for k, v in e.items()
                                        if k != "id"}).split(":")[1]
    return e


def make_task(kind: str, target: str, acceptance: dict) -> dict:
    """TASK: requested state improvement. Completes only via receipts,
    never by assertion."""
    assert kind and target and isinstance(acceptance, dict)
    t = _freeze({"kind": "TASK", "task_kind": kind, "target": target,
                 "acceptance": acceptance, "status": "READY"})
    t["id"] = obj_id("task", {k: v for k, v in t.items() if k != "id"})
    return t


def make_run(task_id: str, worker: str, model: str = "",
             inputs_root: str = "") -> dict:
    """RUN: one concrete attempt. Cost/time/tokens are first-class —
    the economic governor reads them, not prose."""
    assert task_id and worker
    r = _freeze({"kind": "RUN", "task": task_id, "worker": worker,
                 "model": model, "inputs_root": inputs_root,
                 "events_root": "", "outputs_root": "",
                 "tokens": 0, "cost": 0.0, "duration_ms": 0})
    r["id"] = obj_id("run", {k: v for k, v in r.items() if k != "id"})
    return r


def make_gate(gate_id: str, runtime: str, program_hash: str,
              input_schema_hash: str = "") -> dict:
    """GATE reference: versioned id + content-addressed program. New logic
    means a new id; silent edits are protocol violations."""
    assert gate_id and runtime and program_hash
    return _freeze({"kind": "GATE", "id": gate_id, "runtime": runtime,
                    "program_hash": program_hash,
                    "input_schema_hash": input_schema_hash})


def make_grant(subject: str, capability: str, constraints: dict,
               predicates: list, expiry: str, signature: str = "",
               minimum_proof_level: int = 0) -> dict:
    """GRANT: scoped expiring permission. Unsigned grants never authorize
    (fail closed at verify time); pubkey subjects verify cryptographically."""
    assert subject and capability and isinstance(constraints, dict)
    assert isinstance(predicates, list) and expiry
    assert 0 <= minimum_proof_level <= 12
    g = _freeze({"kind": "GRANT", "subject": subject,
                 "capability": capability, "constraints": constraints,
                 "predicates": predicates, "expiry": expiry,
                 "minimum_proof_level": minimum_proof_level,
                 "signature": signature})
    g["id"] = obj_id("grant", {k: v for k, v in g.items() if k != "id"})
    return g
