"""Scheduler: scarce-asset campaigns own external experiment slots.

Invariant (kept absolutely, devplan §3): infrastructure is pulled into the
selected campaign as support and can NEVER outbid an asset campaign for a
scarce account/store/permission. select() enforces it structurally, not by
policy text.
"""
from . import ids


def select(campaigns, slots):
    """campaigns: [{id, kind: asset|infra, value, needs_slot}].
    slots: [slot_ids...] (scarce external permissions).
    Returns {slot: campaign_id}. Asset campaigns fill scarce slots first by
    value; infra attaches only to leftover slots as support, else waits."""
    assets = sorted([c for c in campaigns if c.get("kind") == "asset"],
                    key=lambda c: (-c.get("value", 0), c.get("id", "")))
    infra = sorted([c for c in campaigns if c.get("kind") != "asset"],
                   key=lambda c: (-c.get("value", 0), c.get("id", "")))
    alloc, remaining = {}, list(slots)
    for c in assets:
        if c.get("needs_slot") and remaining:
            alloc[remaining.pop(0)] = c["id"]
    for c in infra:
        if c.get("needs_slot") and remaining:
            alloc[remaining.pop(0)] = c["id"] + ":support"
    record = {"allocation": alloc,
              "unallocated": [c["id"] for c in campaigns
                              if c["id"] not in [v.split(":")[0]
                                                 for v in alloc.values()]]}
    record["allocation_id"] = ids.obj_id("alloc", {"allocation": alloc,
                                                   "slots": slots})
    return record
