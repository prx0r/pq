from __future__ import annotations
import argparse
import json
import random
from pathlib import Path
from typing import Any

from .compiler import SpecCompiler
from .drivers import RecordedDriver, TransformDriver
from .effects import EffectJournal, InjectedCrash
from .metamorphic_suite import run_metamorphic_suite
from .mutation_suite import run_mutation_suite
from .planner_attack_suite import run_planner_attack_suite
from .e2e_suite import run_e2e_suite
from .suite import run_suite
from .policies import FINAL_POLICY
from .underengineer import build_minimal_plan

ROOT=Path(__file__).resolve().parents[1]
SPEC=(ROOT/"specs/ghostcompute_long_spec.md").read_text()
ORACLE=json.loads((ROOT/"fixtures/oracle_ghostcompute.json").read_text())

def _shuffle_oracle(seed: int) -> dict[str,Any]:
    r=random.Random(seed)
    x=json.loads(json.dumps(ORACLE))
    r.shuffle(x["mission"]["mandatory_outcomes"])
    r.shuffle(x["mission"]["constraints"])
    r.shuffle(x["mission"]["non_goals"])
    r.shuffle(x["mission"]["optional_ideas"])
    r.shuffle(x["claims"]["claims"])
    for c in x["claims"]["claims"]:
        c.setdefault("source_refs", [])
        c.setdefault("depends_on", [])
        r.shuffle(c["source_refs"])
        r.shuffle(c["depends_on"])
    for routes in x["routes"]["routes"].values():
        r.shuffle(routes)
    return x

def fuzz_semantic_stability(rounds: int, seed: int) -> dict[str,Any]:
    base_m,base_c=SpecCompiler(RecordedDriver(ORACLE),policy=FINAL_POLICY).compile(SPEC)
    base_tasks=build_minimal_plan(
        base_c,
        machine_capabilities={
            "filesystem.write","shell","qp","xmr","http","security.scan",
            "deploy.test","github.pr.merge"
        },
        human_capabilities={"owner.dns_2fa"},
        policy=FINAL_POLICY,
    )
    base_routes=sorted((t.covers[0],t.route_id) for t in base_tasks)
    failures=[]
    for i in range(rounds):
        o=_shuffle_oracle(seed+i)
        try:
            _,c=SpecCompiler(RecordedDriver(o),policy=FINAL_POLICY).compile(SPEC)
            tasks=build_minimal_plan(
                c,
                machine_capabilities={
                    "filesystem.write","shell","qp","xmr","http","security.scan",
                    "deploy.test","github.pr.merge"
                },
                human_capabilities={"owner.dns_2fa"},
                policy=FINAL_POLICY,
            )
            routes=sorted((t.covers[0],t.route_id) for t in tasks)
            if c.contract_root!=base_c.contract_root or routes!=base_routes:
                failures.append({
                    "round":i,"seed":seed+i,
                    "root_same":c.contract_root==base_c.contract_root,
                    "routes_same":routes==base_routes,
                })
        except Exception as e:
            failures.append({"round":i,"seed":seed+i,"error":repr(e)})
    return {"rounds":rounds,"passed":rounds-len(failures),"failed":len(failures),"failures":failures[:20]}

def fuzz_crash_recovery(rounds: int, seed: int) -> dict[str,Any]:
    r=random.Random(seed)
    failures=[]
    for i in range(rounds):
        journal=EffectJournal()
        key=f"k-{seed}-{i}"
        action={"capability":"demo.effect","value":r.randint(0,100)}
        crash=r.choice(["after_prepare","after_commit",None])
        try:
            journal.execute(action=action,idempotency_key=key,crash_at=crash,policy=FINAL_POLICY)
        except InjectedCrash:
            pass
        try:
            journal.execute(action=action,idempotency_key=key,policy=FINAL_POLICY)
        except Exception as e:
            failures.append({"round":i,"crash":crash,"error":repr(e)})
            continue
        expected=1
        if journal.physical_effect_count!=expected:
            failures.append({"round":i,"crash":crash,"physical_effect_count":journal.physical_effect_count})
    return {"rounds":rounds,"passed":rounds-len(failures),"failed":len(failures),"failures":failures[:20]}

def run_soak(rounds: int = 200, seed: int = 20260914) -> dict[str,Any]:
    base=run_suite(FINAL_POLICY)
    mutation=run_mutation_suite()
    metamorphic=run_metamorphic_suite()
    planner=run_planner_attack_suite()
    e2e=run_e2e_suite()
    semantic=fuzz_semantic_stability(rounds,seed)
    crash=fuzz_crash_recovery(rounds,seed+10_000)
    compact_e2e={k:v for k,v in e2e.items() if k!="run"}
    all_green=all([
        base["failed"]==0,mutation["failed"]==0,metamorphic["failed"]==0,
        planner["failed"]==0,e2e["failed"]==0,
        semantic["failed"]==0,crash["failed"]==0,
    ])
    return {
        "seed":seed,
        "rounds":rounds,
        "all_green":all_green,
        "base":base,
        "mutation":mutation,
        "metamorphic":metamorphic,
        "planner":planner,
        "e2e":compact_e2e,
        "semantic_fuzz":semantic,
        "crash_fuzz":crash,
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--rounds",type=int,default=200)
    p.add_argument("--seed",type=int,default=20260914)
    args=p.parse_args(argv)
    out=run_soak(args.rounds,args.seed)
    print(json.dumps(out,indent=2))
    raise SystemExit(0 if out["all_green"] else 1)

if __name__=="__main__":
    main()
