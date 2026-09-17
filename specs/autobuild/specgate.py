"""Compiler spec gate (PROMOTED to canonical 2026-09-14).

Provenance: semantics promoted from ab1.specgate (plan/acceptance/declared
evidence — no trust-only features) and ab3 covers mapping (feature→goal
index, non-empty, valid). Fresh implementation (compact union); frozen
sources untouched. Seesaw scoring stays separate and advisory.
"""


def check_plan(plan):
    errors = []
    if not isinstance(plan, dict):
        return {"ok": False, "errors": ["plan must be an object"]}
    goal = plan.get("goal")
    if not isinstance(goal, dict):
        errors.append("goal missing")
        goal = {}
    if not goal.get("statement"):
        errors.append("goal.statement missing")
    acc = goal.get("acceptance", [])
    if not acc:
        errors.append("goal.acceptance missing/empty")
    feats = plan.get("features")
    if not isinstance(feats, list) or not feats:
        errors.append("features missing/empty")
    else:
        for i, f in enumerate(feats):
            if not isinstance(f, dict):
                errors.append("features[%d] must be an object" % i)
                continue
            fid = f.get("id", "features[%d]" % i)
            if not f.get("description"):
                errors.append("%s: description missing" % fid)
            if not f.get("acceptance"):
                errors.append("%s: acceptance missing" % fid)
            ev = f.get("evidence")
            if not isinstance(ev, list) or not ev:
                errors.append("%s: declared evidence missing "
                              "(no trust-only features)" % fid)
            else:
                for j, e in enumerate(ev):
                    if (not isinstance(e, dict) or not e.get("kind")
                            or not e.get("ref")):
                        errors.append("%s: evidence[%d] needs kind+ref"
                                      % (fid, j))
            covers = f.get("covers", [])
            if not isinstance(covers, list) or not covers:
                errors.append("%s: covers missing/empty "
                              "(map to goal indices)" % fid)
            else:
                for c in covers:
                    if not isinstance(c, int) or c < 0 or c >= len(acc):
                        errors.append("%s: covers bad index %r" % (fid, c))
    return {"ok": not errors, "errors": errors}


def check_plugin(spec):
    errors, warnings = [], []
    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["spec must be an object"],
                "warnings": []}
    for field in ("name", "version"):
        if not spec.get(field):
            errors.append("plugin.%s missing" % field)
    tools = spec.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("plugin.tools missing/empty")
    else:
        for i, t in enumerate(tools):
            tid = t.get("name", "tools[%d]" % i) if isinstance(t, dict) else \
                "tools[%d]" % i
            if not isinstance(t, dict) or not t.get("name") or \
                    not t.get("description"):
                errors.append("%s: needs name+description" % tid)
            if isinstance(t, dict) and (t.get("third_party") or
                                        t.get("auth")):
                ledger = t.get("provider")
                if (not isinstance(ledger, dict) or not ledger.get("name")
                        or not ledger.get("tos")):
                    errors.append("%s: third-party/auth tool needs "
                                  "provider{name, tos}" % tid)
                else:
                    warnings.append("%s: verify provider ToS + value-add" % tid)
    return {"ok": not errors, "errors": errors, "warnings": warnings}
