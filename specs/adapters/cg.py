"""CG adapter: cogymkernel as canonical experiment executor (reference).

CG owns: deterministic runs, content-addressed RunReceipts, hard gates,
evolution recipes, experience. We own: contracts, truth, scheduling.
Adapter surface: version pin, executor smoke (proves the import path live),
lane->worldpack manifest translation. Full AsyncRunner episodes stay in
/cg (run there, bank receipts here) — never reimplemented.
"""
import os
import subprocess
import sys

from adapters import _env

CG_DEFAULT = "/home/ubuntu/cg"


def root():
    return _env.require_dir(
        _env.repo_root("AGENTCOM_CG_ROOT", CG_DEFAULT), "cg")


def version():
    try:
        r = root()
        rev = subprocess.run(["git", "-C", r, "rev-parse", "HEAD"],
                             capture_output=True, text=True,
                             timeout=10).stdout.strip()
        available = True
    except Exception:  # noqa: BLE001
        r, rev, available = _env.repo_root("AGENTCOM_CG_ROOT",
                                           CG_DEFAULT), "unknown", False
    return {"repo": r, "rev": rev, "available": available,
            "kernel": "cogymkernel",
            "receipt": "content-addressed RunReceipt"}


def _import():
    r = root()
    if r not in sys.path:
        sys.path.insert(0, r)
    import cogym_kernel  # noqa: E402
    return cogym_kernel


def smoke():
    """Prove the import + executor path live: one deterministic action."""
    _import()
    from cogym_kernel import executors
    from cogym_kernel.kernel import contracts as _c
    action = _c.ActionSpec(kind="smoke", payload={"echo": "hi"},
                           estimated_cost=0.0)
    result = executors.DeterministicExecutor().execute(action)
    return {"executor": "det-v1", "status": result.status,
            "request_hash": result.request_hash,
            "response_hash": result.response_hash}


def lane_to_worldpack(contract_root, candidate_sha, policy_id, seed=7):
    """Translate a Seed0 lane into a cg worldpack-ish manifest (reference
    shape for running inside /cg; executed there, not here)."""
    return {"worldpack": "agentcom-lane",
            "scenario": {"contract_root": contract_root,
                         "candidate_sha": candidate_sha,
                         "policy_id": policy_id, "seed": seed},
            "candidate": {"sha": candidate_sha, "policy": policy_id}}


def run_episode(contract_root, candidate_sha, policy_id="toy.cautious_v1",
                seed=7, instance_id="ep-0"):
    """REAL CG execution: AsyncRunner + shipped toy world + bundled policy.
    CG itself emits the RunReceipt (content-addressed run_id). The toy
    domain is declared openly — what is real here is the execution path
    (runner loop, gates-shaped metrics, receipt identity), not the domain.
    Returns {run_id, events_root, metrics, worldpack_id, ...}."""
    import asyncio as _asyncio
    _import()
    from cogym_kernel import executors as _ex
    from cogym_kernel.kernel import runner as _runner
    from cogym_kernel.worlds import toy as _toy
    policies = {"toy.cautious_v1": _toy.CautiousPolicy}
    if policy_id not in policies:
        raise ValueError("unknown-policy:%s (available: toy.cautious_v1)"
                         % policy_id)
    runner = _runner.AsyncRunner(
        _runner.ExecutorRegistry(
            {"deterministic": _ex.DeterministicExecutor()}))
    receipt = _asyncio.run(runner.run_episode(
        _toy.SignalWorld(), policies[policy_id](), instance_id=instance_id,
        seed=seed))
    metrics = {m.name: m.value for m in receipt.metrics.metrics}
    return {"run_id": receipt.run_id,
            "events_root": receipt.events_root,
            "metrics": metrics,
            "worldpack_id": receipt.worldpack_id,
            "contract_root": contract_root, "candidate_sha": candidate_sha,
            "policy_id": policy_id, "seed": seed,
            "mode": "CG_REAL_RUNNER_TOY_DOMAIN"}


def run_lane(contract_root, candidate_sha, policy_id, work_fn, seed=7,
             base_sha=""):
    """Minimal lane execution through CG primitives: run the lane function
    (AgentCom-side work), then wrap the outcome as a CG-style RunReceipt
    reference {run_id (content-addressed), contract, candidate, policy,
    seed, events_root, metrics}. CG = experiment record; QP (elsewhere)
    remains truth. work_fn() -> {events[{kind, hash}], metrics{...}}."""
    _import()
    from cogym_kernel.kernel import ids as _ids
    out = work_fn() or {}
    events = out.get("events", [])
    event_hashes = [e if isinstance(e, str) else _ids.content_id(
        "event", {"kind": e.get("kind", "?"),
                  "hash": e.get("hash", "?")}) for e in events]
    events_root = _ids.events_root(event_hashes) if hasattr(_ids, "events_root") \
        else _ids.content_id("events", event_hashes)
    receipt = {"worldpack": "agentcom-lane",
               "scenario": {"contract_root": contract_root,
                            "candidate_sha": candidate_sha,
                            "policy_id": policy_id, "seed": seed,
                            "base_sha": base_sha},
               "candidate": {"sha": candidate_sha, "policy": policy_id},
               "events_root": events_root,
               "metrics": out.get("metrics", {})}
    receipt["run_id"] = _ids.content_id("run", {
        "worldpack": receipt["worldpack"], "scenario": receipt["scenario"],
        "candidate": candidate_sha, "seed": seed,
        "events_root": events_root})
    return receipt
