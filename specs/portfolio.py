"""Portfolio: thin campaign registry. AgentCom owns WHAT NEXT; selection
requires an accepted StrategicDecision ref and goes through the scheduler.
No campaign executes from here — execution lives in A-Task (adapter)."""
from . import ids, scheduler


class BadCampaign(ValueError):
    pass


def register(campaigns, campaign):
    if not isinstance(campaign, dict) or not campaign.get("id"):
        raise BadCampaign("campaign needs id")
    if campaign.get("kind") not in ("asset", "infra"):
        raise BadCampaign("kind must be asset|infra")
    campaigns = dict(campaigns)
    campaigns[campaign["id"]] = campaign
    return campaigns


def select_next(campaigns, slots, strategic_ref):
    """strategic_ref: StrategicRoot that admits this round. Returns the
    scheduler allocation bound to that decision (reference, not truth)."""
    if not strategic_ref:
        raise BadCampaign("selection needs an accepted StrategicDecision ref")
    alloc = scheduler.select(list(campaigns.values()), slots)
    alloc["strategic_ref"] = strategic_ref
    alloc["selection_id"] = ids.obj_id("selection", {
        "allocation": alloc["allocation"], "strategic_ref": strategic_ref})
    return alloc
