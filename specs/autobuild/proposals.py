"""Proposal channel (devplan §7). Fresh implementation.

Agent next-tasks are PROPOSALS, never work orders: they carry binding:none
until the scheduler binds them to requirements with an expected-Actuality
calculation. bind() refuses unbound proposals presented as READY, and the
compiler output shape contains no A-Task fields (no ids, no DONE) so it
cannot be mistaken for a work queue.
"""

PROPOSAL = "binding:none"


def propose(task, justification, expected_delta=None):
    return {"task": task, "justification": justification,
            "expected_actuality_delta": expected_delta, "binding": None,
            "channel": "proposal"}


def bind(proposal, requirement_id, scheduler_ref):
    """Scheduler binding: proposal + requirement + expected delta + ref."""
    if not isinstance(proposal, dict) or proposal.get("binding") is not None:
        return None
    if not requirement_id or not scheduler_ref:
        return None
    bound = dict(proposal)
    bound["binding"] = {"requirement": requirement_id,
                        "scheduler_ref": scheduler_ref}
    bound["channel"] = "bound"
    return bound


def is_work_order(obj):
    """True if obj looks like an executable work order (must never be true
    of raw compiler output)."""
    if not isinstance(obj, dict):
        return False
    return any(k in obj for k in ("task_id", "status", "DONE", "atask_id"))
