"""Seesaw adapter: strategy feed for the scheduler. Thin by design —
scoring lives in autobuild/compiler/seesaw.py; this adapter only binds an
accepted proposal to a StrategicRoot reference for portfolio selection."""
from autobuild.compiler import seesaw as _s
from core import ids


def propose(project, features):
    return _s.propose(project, features)


def accept(proposal):
    """Acceptance mints the StrategicRoot (scheduler/human act, recorded)."""
    decision = dict(proposal)
    decision["status"] = "ACCEPTED"
    decision["strategic_root"] = ids.obj_id("strategic", {
        "project": proposal.get("project"),
        "binding": proposal.get("binding"),
        "first_moat_event": proposal.get("first_moat_event")})
    return decision
