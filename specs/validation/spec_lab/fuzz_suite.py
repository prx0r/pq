from __future__ import annotations
import json, random
from pathlib import Path
from .compiler import SpecCompiler
from .drivers import RecordedDriver, TransformDriver
from .effects import EffectJournal, InjectedCrash
from .policies import FINAL_POLICY
from .underengineer import build_minimal_plan
from .validation import ContractError

ROOT=Path(__file__).resolve().parents[1]
SPEC=(ROOT/"specs/ghostcompute_long_spec.md").read_text()
ORACLE=json.loads((ROOT/"fixtures/oracle_ghostcompute.json").read_text())

def _compile(transforms):
    return SpecCompiler(
        TransformDriver(RecordedDriver(ORACLE), transforms),
        policy=FINAL_POLICY,
    ).compile(SPEC)

def run_compiler_fuzz(trials=1000, seed=20260914):
    rng=random.Random(seed)
    mutation_names=[
        "self_true","missing_proof","bad_source","negative_cost","unknown_kind",
        "optional_scope","budget_inflate","already_true_route","claim_cycle"
    ]
    blocked=0
    details={k:{"trials":0,"safe":0} for k in mutation_names}

    for i in range(trials):
        kind=rng.choice(mutation_names)
        details[kind]["trials"]+=1

        if kind=="self_true":
            def mut_claims(out):
                x=json.loads(json.dumps(out))
                c=rng.choice([c for c in x["claims"] if c["kind"]=="leaf"])
                c["state"]="TRUE"
                return x
            try:
                _,contract=_compile({"claims":mut_claims})
                tasks=build_minimal_plan(contract)
                # The chosen leaf's exact identity varies. Safety property:
                # compiler-origin TRUE must be ignored globally.
                safe=all(c.state=="UNKNOWN" for c in contract.claims if c.kind=="leaf")
            except ContractError:
                safe=True

        elif kind=="missing_proof":
            def mut_claims(out):
                x=json.loads(json.dumps(out))
                rng.choice([c for c in x["claims"] if c["kind"]=="leaf"])["proof_id"]=None
                return x
            try:
                _compile({"claims":mut_claims}); safe=False
            except ContractError: safe=True

        elif kind=="bad_source":
            def mut_claims(out):
                x=json.loads(json.dumps(out))
                rng.choice([c for c in x["claims"] if c["kind"]=="leaf"])["source_refs"]=[f"§{9000+i}"]
                return x
            try:
                _compile({"claims":mut_claims}); safe=False
            except ContractError: safe=True

        elif kind=="negative_cost":
            def mut_routes(out):
                x=json.loads(json.dumps(out))
                key=rng.choice(list(x["routes"]))
                x["routes"][key][0]["cost_usd"]=-rng.random()*100
                return x
            try:
                _compile({"routes":mut_routes}); safe=False
            except ContractError: safe=True

        elif kind=="unknown_kind":
            def mut_routes(out):
                x=json.loads(json.dumps(out))
                key=rng.choice(list(x["routes"]))
                x["routes"][key][0]["kind"]="MAGIC_"+str(i)
                return x
            try:
                _compile({"routes":mut_routes}); safe=False
            except ContractError: safe=True

        elif kind=="optional_scope":
            def mut_mission(out):
                x=json.loads(json.dumps(out))
                idea=rng.choice(x["optional_ideas"])
                x["mandatory_outcomes"].append({
                    "id":f"optional_{i}",
                    "statement":str(idea),
                    "source_refs":["§16"],
                })
                return x
            try:
                _compile({"mission":mut_mission}); safe=False
            except ContractError: safe=True

        elif kind=="budget_inflate":
            def mut_mission(out):
                x=json.loads(json.dumps(out))
                x["budget"]["usd"]=20+rng.randint(1,100000)
                return x
            try:
                _compile({"mission":mut_mission}); safe=False
            except ContractError: safe=True

        elif kind=="already_true_route":
            def mut_routes(out):
                x=json.loads(json.dumps(out))
                key=rng.choice(list(x["routes"]))
                x["routes"][key].insert(0,{
                    "id":f"fake_true_{i}","kind":"ALREADY_TRUE",
                    "cost_usd":0,"time_minutes":0,"human_minutes":0,
                    "irreversibility":0,"complexity":0,"information_gain":0,
                    "capabilities":[],"admissible":True
                })
                return x
            _,contract=_compile({"routes":mut_routes})
            tasks=build_minimal_plan(contract)
            safe=all(t.route_id!=f"fake_true_{i}" for t in tasks)

        else: # claim_cycle
            def mut_claims(out):
                x=json.loads(json.dumps(out))
                x["claims"] += [
                    {"id":f"root.cycle.a{i}","statement":"a","kind":"root","mandatory":True,
                     "depends_on":[f"root.cycle.b{i}"],"logic":"ALL","source_refs":["§1"]},
                    {"id":f"root.cycle.b{i}","statement":"b","kind":"root","mandatory":True,
                     "depends_on":[f"root.cycle.a{i}"],"logic":"ALL","source_refs":["§1"]},
                ]
                return x
            try:
                _compile({"claims":mut_claims}); safe=False
            except ContractError: safe=True

        if safe:
            blocked+=1
            details[kind]["safe"]+=1

    return {
        "trials":trials,
        "safe":blocked,
        "seed":seed,
        "classes":details,
    }

def run_crash_fuzz(trials=500, seed=20260914):
    rng=random.Random(seed)
    safe=0
    cases={"before":0,"after_prepare":0,"after_commit":0,"normal":0}
    for i in range(trials):
        crash=rng.choice(["before","after_prepare","after_commit","normal"])
        cases[crash]+=1
        j=EffectJournal()
        action={"capability":"external.mutate","n":i}
        key=f"k{i}"
        if crash=="before":
            # No first call happened; resume once.
            j.execute(action=action,idempotency_key=key,policy=FINAL_POLICY)
        elif crash=="normal":
            j.execute(action=action,idempotency_key=key,policy=FINAL_POLICY)
            j.execute(action=action,idempotency_key=key,policy=FINAL_POLICY)
        else:
            try:
                j.execute(
                    action=action,idempotency_key=key,
                    crash_at=crash,policy=FINAL_POLICY
                )
            except InjectedCrash:
                pass
            j.execute(action=action,idempotency_key=key,policy=FINAL_POLICY)
        if j.physical_effect_count==1:
            safe+=1
    return {"trials":trials,"safe":safe,"seed":seed,"cases":cases}

def run_all():
    return {
        "compiler":run_compiler_fuzz(),
        "crash":run_crash_fuzz(),
    }

if __name__=="__main__":
    print(json.dumps(run_all(),indent=2))
