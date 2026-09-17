from __future__ import annotations
import json, random
from pathlib import Path
from .compiler import SpecCompiler
from .drivers import RecordedDriver, TransformDriver
from .policies import FINAL_POLICY

ROOT=Path(__file__).resolve().parents[1]
SPEC=(ROOT/"specs/ghostcompute_long_spec.md").read_text()
ORACLE=json.loads((ROOT/"fixtures/oracle_ghostcompute.json").read_text())

def baseline():
    return SpecCompiler(RecordedDriver(ORACLE),policy=FINAL_POLICY).compile(SPEC)

def compile_with(stage,fn):
    d=TransformDriver(RecordedDriver(ORACLE),{stage:fn})
    return SpecCompiler(d,policy=FINAL_POLICY).compile(SPEC)

def case_claim_order():
    _,base=baseline()
    def mut(out):
        x=json.loads(json.dumps(out));x["claims"]=list(reversed(x["claims"]));return x
    _,other=compile_with("claims",mut)
    return base.contract_root==other.contract_root, f"{base.contract_root} vs {other.contract_root}"

def case_route_order():
    _,base=baseline()
    def mut(out):
        x=json.loads(json.dumps(out))
        for k,v in x["routes"].items(): x["routes"][k]=list(reversed(v))
        return x
    _,other=compile_with("routes",mut)
    return base.contract_root==other.contract_root, f"{base.contract_root} vs {other.contract_root}"

def case_route_addition():
    _,base=baseline()
    def mut(out):
        x=json.loads(json.dumps(out))
        x["routes"]["leaf.quote"].append({
            "id":"alternate-valid-implementation","kind":"BUILD","cost_usd":10,
            "time_minutes":120,"human_minutes":0,"irreversibility":0,
            "complexity":5,"information_gain":0,"capabilities":[],"admissible":True
        })
        return x
    _,other=compile_with("routes",mut)
    return base.contract_root==other.contract_root, f"{base.contract_root} vs {other.contract_root}"

def case_mission_outcome_order():
    m1,c1=baseline()
    def mut(out):
        x=json.loads(json.dumps(out));x["mandatory_outcomes"]=list(reversed(x["mandatory_outcomes"]));return x
    m2,c2=compile_with("mission",mut)
    return m1.mission_id==m2.mission_id and c1.contract_root==c2.contract_root, f"{c1.contract_root} vs {c2.contract_root}"

def case_source_ref_order():
    _,base=baseline()
    def mut(out):
        x=json.loads(json.dumps(out))
        for c in x["claims"]: c["source_refs"]=list(reversed(c.get("source_refs",[])))
        return x
    _,other=compile_with("claims",mut)
    return base.contract_root==other.contract_root, f"{base.contract_root} vs {other.contract_root}"

CASES=[
    ("claim_order","Claim serialization order must not change ContractRoot",case_claim_order),
    ("route_order","Route proposal order must not change ContractRoot",case_route_order),
    ("route_addition","Adding an implementation alternative must not change acceptance ContractRoot",case_route_addition),
    ("mission_outcome_order","Mandatory outcome ordering must not change semantic ContractRoot",case_mission_outcome_order),
    ("source_ref_order","Source-ref ordering must not change ContractRoot",case_source_ref_order),
]

def run_metamorphic_suite():
    rows=[]
    for mid,hyp,fn in CASES:
        try:
            ok,detail=fn()
        except Exception as e:
            ok,detail=False,f"uncaught {type(e).__name__}: {e}"
        rows.append({"id":mid,"hypothesis":hyp,"pass":bool(ok),"detail":detail})
    return {
        "passed":sum(x["pass"] for x in rows),
        "failed":sum(not x["pass"] for x in rows),
        "total":len(rows),
        "rows":rows,
    }
