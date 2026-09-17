"""8-root lineage (+ optional promotion receipt). Every root is a full
SHA-256 content id (core.ids). Nothing compressed to preserve '7'.

StrategicRoot = hash(Seesaw StrategicDecision)
CampaignRoot  = hash(project + scarce asset + experiment objective)
ContractRoot  = hash(WHAT must become true)
PlanRoot      = hash(HOW we currently intend to achieve it)
RunRoot       = hash(one execution attempt)
EvidenceRoot  = hash(what was actually observed)
QPReceiptID   = QP-settled transition id (reference, minted by QP)
OutcomeRoot   = hash(downstream real consequence)
PromotionReceiptID (optional) = governed promotion of a lesson/primitive.
"""
from . import ids


def root(prefix, obj):
    return ids.obj_id(prefix, obj)


def build_chain(strategic, campaign, contract, plan, run, evidence,
                qp_receipt_id, outcome, promotion=None):
    chain = {
        "strategic": root("strategic", strategic),
        "campaign": root("campaign", campaign),
        "contract": root("contract", contract),
        "plan": root("plan", plan),
        "run": root("run", run),
        "evidence": root("evidence", evidence),
        "qp_receipt": qp_receipt_id,
        "outcome": root("outcome", outcome),
    }
    if promotion is not None:
        chain["promotion"] = root("promotion", promotion)
    return chain


def verify_chain(chain, parts):
    """Recompute every root except qp_receipt (QP-minted reference, verified
    against QP itself). parts maps root-name -> original object. Returns
    (ok, failures[])."""
    fails = []
    for name in ("strategic", "campaign", "contract", "plan", "run",
                 "evidence", "outcome"):
        if name not in parts:
            fails.append("missing-part:%s" % name)
            continue
        if chain.get(name) != root(name, parts[name]):
            fails.append("mismatch:%s" % name)
    if "promotion" in chain:
        if "promotion" not in parts:
            fails.append("missing-part:promotion")
        elif chain["promotion"] != root("promotion", parts["promotion"]):
            fails.append("mismatch:promotion")
    if not chain.get("qp_receipt"):
        fails.append("missing:qp_receipt")
    return (not fails), fails


def contract_invariant(old_chain, new_chain):
    """Prebuild route change: PlanRoot must change, ContractRoot must not."""
    if old_chain.get("contract") != new_chain.get("contract"):
        return False, "contract-changed"
    if old_chain.get("plan") == new_chain.get("plan"):
        return False, "plan-unchanged"
    return True, "reuse-applied"
