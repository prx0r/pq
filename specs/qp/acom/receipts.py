"""TransitionReceipt: the ONE canonical output (northstar §3).

Everything meaningful emits the same artifact: canonical JSON, hashed,
signed (signature field carried; key management lives above the kernel).
`transition()` is the ONLY path from proposal to canonical state:

    S[t+1] = T(S[t], P)  iff  ALL gates PASS  (northstar §1)

No gate pass, no transition. No prose anywhere in the artifact
(invariant 8). Receipts carry proof_level V0..V12 (northstar §5);
authority maps capability -> minimum level.
"""

from . import gates
from .canonical import PROTOCOL, canonical, sha256_hex


def transition(state_before: dict, proposal: dict, evidence: list,
               gate_ids: list, run: dict, proof_level: int = 0,
               transition_type: str = "RESOLVE",
               apply=None) -> dict:
    """Evaluate gates; on all-PASS compute post-state via apply().

    apply(state_before, proposal, evidence) -> state_after dict.
    Returns the receipt in ALL cases (FAIL receipts are first-class:
    they record exactly what did not pass).
    """
    assert 0 <= proof_level <= 12
    inputs = {"claim": proposal.get("claim", proposal),
              "evidence": evidence}
    results = [gates.execute(g, inputs) for g in gate_ids]
    passed = all(r["result"] == "PASS" for r in results)
    state_after = (apply(state_before, proposal, evidence)
                   if (passed and apply) else dict(state_before))
    receipt = {
        "protocol": PROTOCOL,
        "transition_type": transition_type,
        "proof_level": proof_level,
        "subject": proposal.get("id", proposal.get("target", "?")),
        "state_before": state_before,
        "proposal": proposal,
        "evidence_root": _root_of(evidence),
        "gates": results,
        "grant": proposal.get("grant"),
        "run": run,
        "state_after": state_after,
        "passed": passed,
    }
    receipt["id"] = "receipt:" + sha256_hex(canonical(
        {k: v for k, v in receipt.items()
         if k not in ("id", "signature")}))[:16]
    receipt["signature"] = ""  # authority layer signs; kernel never forges
    return receipt


def _root_of(evidence: list) -> str:
    from .canonical import merkle_root
    return merkle_root([e.get("id", "?") for e in evidence])


def sign_receipt(secret: bytes, receipt: dict) -> dict:
    """Authority signs the settled id. `signer` (pubkey hex) rides
    OUTSIDE the hashed body: the id commits to content, the signature
    commits the signer to the id. Kernel never calls this itself."""
    from . import crypto as _crypto
    out = dict(receipt)
    _sec, pub = _crypto.keypair(secret)
    out["signer"] = pub.hex()
    out["signature"] = _crypto.sign_id(secret, out["id"])
    return out


def verify_receipt(receipt: dict) -> dict:
    """Recompute id + re-run gates. Independent re-evaluation
    (invariant 11): the verifier trusts nothing but the bytes."""
    if receipt.get("protocol") != PROTOCOL:
        return {"ok": False, "reason": "protocol mismatch"}
    want = "receipt:" + sha256_hex(canonical(
        {k: v for k, v in receipt.items()
         if k not in ("id", "signature", "signer")}))[:16]
    if receipt.get("id") != want:
        return {"ok": False, "reason": "receipt id mismatch (tampered?)"}
    if receipt.get("signer"):
        from . import crypto as _crypto
        if not _crypto.verify_id(receipt["signer"], receipt["id"],
                                 receipt.get("signature", "")):
            return {"ok": False, "reason": "bad receipt signature"}
    return {"ok": True, "reason": "id recomputes; re-run gates to settle PASS"}


def settle(receipt: dict, evidence: list) -> dict:
    """Full independent settlement: id check + every gate re-executed."""
    v = verify_receipt(receipt)
    if not v["ok"]:
        return v
    inputs = {"claim": receipt["proposal"].get("claim", receipt["proposal"]),
              "evidence": evidence}
    for g in receipt.get("gates", []):
        r = gates.execute(g["id"], inputs)
        if r["result"] != g["result"]:
            return {"ok": False,
                    "reason": f"gate {g['id']} disagrees on replay"}
    passed = all(g["result"] == "PASS" for g in receipt.get("gates", []))
    return {"ok": passed, "reason": "all gates replay identically"}
