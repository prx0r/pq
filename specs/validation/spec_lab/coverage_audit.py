from __future__ import annotations
from dataclasses import asdict
from typing import Any

def audit_obligations(mission, contract, gold: dict[str,Any]) -> dict[str,Any]:
    corpus=" ".join([
        mission.intent,
        *[str(x.get("statement","")) for x in mission.mandatory_outcomes],
        *[str(x) for x in mission.constraints],
        *[c.statement for c in contract.claims],
        *[str(c.proof_id or "") for c in contract.claims],
    ]).lower()
    rows=[]
    for item in gold.get("obligations",[]):
        needles=[str(x).lower() for x in item.get("needles",[])]
        found=any(n in corpus for n in needles)
        rows.append({
            "id":item["id"],
            "required":bool(item.get("required",True)),
            "found":found,
            "needles":needles,
        })
    required=[x for x in rows if x["required"]]
    return {
        "passed":sum(x["found"] for x in required),
        "total":len(required),
        "missing":[x["id"] for x in required if not x["found"]],
        "rows":rows,
    }
