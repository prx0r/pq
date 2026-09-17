"""Deterministic gates (northstar §4, §41 invariant 4).

A gate is versioned, content-addressed logic: same inputs ALWAYS give
the same verdict. Registry maps gate id -> pure predicate function.
`program_hash` pins the exact predicate source; changing logic means a
new gate id, never a silent edit (invariant 5).

WASM is the declared runtime ABI (schemas/acom.json). This kernel ships
native Python predicates behind the same interface so Phase A runs with
zero toolchain; a WASM runner satisfies the identical call contract.
"""

import hashlib
import inspect

REGISTRY = {}


def gate(gate_id: str):
    """Decorator: register a pure predicate as a versioned gate."""
    def wrap(fn):
        src = inspect.getsource(fn)
        REGISTRY[gate_id] = {
            "fn": fn,
            "program_hash": "sha256:" + hashlib.sha256(
                src.encode()).hexdigest(),
        }
        return fn
    return wrap


def program_hash(gate_id: str) -> str:
    """Content address of a registered gate's predicate source."""
    return REGISTRY[gate_id]["program_hash"]


def execute(gate_id: str, inputs: dict) -> dict:
    """Run one gate. Returns {id, result: PASS|FAIL, proof}."""
    if gate_id not in REGISTRY:
        return {"id": gate_id, "result": "FAIL",
                "proof": "unknown gate id"}
    try:
        ok, proof = REGISTRY[gate_id]["fn"](inputs)
        return {"id": gate_id,
                "result": "PASS" if ok else "FAIL",
                "proof": str(proof)}
    except Exception as e:  # gates never throw outward
        return {"id": gate_id, "result": "FAIL",
                "proof": f"gate raised: {e!r}"}


# --- Built-in gates: the smallest useful set ---------------------------

@gate("two-sources-v1")
def _two_sources(inputs: dict):
    """PASS iff >= 2 distinct accepted sources support the claim."""
    srcs = {e.get("source", {}).get("class", "?")
            for e in inputs.get("evidence", [])}
    srcs.discard("?")
    return len(srcs) >= 2, f"distinct sources: {sorted(srcs)}"


@gate("claim-resolved-v1")
def _claim_resolved(inputs: dict):
    """PASS iff the claim result is not UNKNOWN (invariant 6 enforced
    by callers: absence stays UNKNOWN, never FALSE)."""
    r = (inputs.get("claim") or {}).get("result")
    return r in ("TRUE", "FALSE"), f"claim result: {r}"


@gate("evidence-fresh-v1")
def _evidence_fresh(inputs: dict):
    """PASS iff every evidence item carries metric, value, as_of."""
    for e in inputs.get("evidence", []):
        if not (e.get("metric") and e.get("as_of")
                and "value" in e):
            return False, f"incomplete evidence: {e.get('id')}"
    return True, f"{len(inputs.get('evidence', []))} items complete"


@gate("no-duplicate-v1")
def _no_duplicate(inputs: dict):
    """PASS iff no two evidence items share an id (invariant 14)."""
    ids = [e.get("id") for e in inputs.get("evidence", [])]
    return len(ids) == len(set(ids)), f"{len(ids)} items, {len(set(ids))} unique"
