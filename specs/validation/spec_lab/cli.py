from __future__ import annotations
import argparse, json
from dataclasses import asdict
from pathlib import Path

from .compiler import SpecCompiler
from .drivers import RecordedDriver, CommandDriver, OpenAICompatibleDriver
from .policies import FINAL_POLICY
from .underengineer import build_minimal_plan, ordered
from .suite import run_suite
from .mutation_suite import run_mutation_suite
from .fuzz_suite import run_all as run_fuzz

DEFAULT_MACHINE = [
    "filesystem.write","shell","qp","xmr","http","security.scan",
    "deploy.test","github.pr.merge"
]
DEFAULT_HUMAN = ["owner.dns_2fa"]

def _driver_from(args):
    recorded=getattr(args,"recorded",None)
    command=getattr(args,"driver_command",None)
    compatible=getattr(args,"openai_compatible",False)
    driver=getattr(args,"driver",None)
    oracle=getattr(args,"oracle",None)

    if recorded:
        return RecordedDriver(recorded)
    if command:
        return CommandDriver(command)
    if compatible:
        return OpenAICompatibleDriver()
    if driver=="command":
        if not command:
            raise SystemExit("--driver-command required")
        return CommandDriver(command)
    if driver=="openai-compatible":
        return OpenAICompatibleDriver()
    return RecordedDriver(
        oracle or str(Path(__file__).resolve().parents[1]/"fixtures"/"oracle_ghostcompute.json")
    )

def _caps(args):
    repeated_m=getattr(args,"machine_capability",None)
    repeated_h=getattr(args,"human_capability",None)
    csv_m=getattr(args,"machine_capabilities",None)
    csv_h=getattr(args,"human_capabilities",None)
    machine=set(repeated_m or [])
    human=set(repeated_h or [])
    if csv_m:
        machine.update(x.strip() for x in csv_m.split(",") if x.strip())
    if csv_h:
        human.update(x.strip() for x in csv_h.split(",") if x.strip())
    if not machine:
        machine=set(DEFAULT_MACHINE)
    if not human:
        human=set(DEFAULT_HUMAN)
    return machine,human

def _compile_plan(args):
    raw=Path(args.spec).read_text(encoding="utf-8")
    compiler=SpecCompiler(_driver_from(args),policy=FINAL_POLICY)
    mission,contract=compiler.compile(raw)
    machine,human=_caps(args)
    tasks=ordered(build_minimal_plan(
        contract,machine_capabilities=machine,human_capabilities=human,policy=FINAL_POLICY
    ))
    return mission,contract,tasks

def cmd_compile(args):
    mission,contract,tasks=_compile_plan(args)
    out={
        "mission":asdict(mission),
        "contract":asdict(contract),
        "tasks":[asdict(t) for t in tasks],
    }
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "output":str(target),
        "contract_root":contract.contract_root,
        "claims":len(contract.claims),
        "tasks":len(tasks),
    },indent=2))

def cmd_plan(args):
    mission,contract,tasks=_compile_plan(args)
    run_dir=Path(args.run_dir)
    run_dir.mkdir(parents=True,exist_ok=True)
    (run_dir/"mission.json").write_text(json.dumps(asdict(mission),indent=2)+"\n")
    (run_dir/"contract.json").write_text(json.dumps(asdict(contract),indent=2)+"\n")
    (run_dir/"tasks.json").write_text(json.dumps([asdict(t) for t in tasks],indent=2)+"\n")
    blocked=[t.id for t in tasks if t.state.startswith("BLOCKED")]
    print(json.dumps({
        "run_dir":str(run_dir.resolve()),
        "mission_id":mission.mission_id,
        "contract_root":contract.contract_root,
        "claims":len(contract.claims),
        "tasks":len(tasks),
        "blocked":blocked,
    },indent=2))

def cmd_test(args):
    main=run_suite(FINAL_POLICY)
    mutations=run_mutation_suite()
    fuzz=run_fuzz()
    print(json.dumps({
        "main":f'{main["passed"]}/{main["total"]}',
        "mutations":f'{mutations["passed"]}/{mutations["total"]}',
        "compiler_fuzz":f'{fuzz["compiler"]["safe"]}/{fuzz["compiler"]["trials"]}',
        "crash_fuzz":f'{fuzz["crash"]["safe"]}/{fuzz["crash"]["trials"]}',
    },indent=2))
    if main["failed"] or mutations["failed"] or fuzz["compiler"]["safe"]!=fuzz["compiler"]["trials"] or fuzz["crash"]["safe"]!=fuzz["crash"]["trials"]:
        raise SystemExit(1)

def _add_driver_options(p):
    p.add_argument("--recorded")
    p.add_argument("--driver-command")
    p.add_argument("--openai-compatible",action="store_true")
    p.add_argument("--driver",choices=["recorded","command","openai-compatible"])
    p.add_argument("--oracle")

def _add_cap_options(p):
    p.add_argument("--machine-capability",action="append")
    p.add_argument("--human-capability",action="append")
    p.add_argument("--machine-capabilities")
    p.add_argument("--human-capabilities")

def main():
    p=argparse.ArgumentParser(prog="agentcom-lab")
    sub=p.add_subparsers(dest="cmd",required=True)

    plan=sub.add_parser("plan",help="paste a long spec -> frozen proof graph + minimal bounded task plan")
    plan.add_argument("spec")
    _add_driver_options(plan); _add_cap_options(plan)
    plan.add_argument("--run-dir",default="run/plan")
    plan.set_defaults(fn=cmd_plan)

    c=sub.add_parser("compile",help="compile long technical spec to one JSON artifact")
    c.add_argument("spec")
    _add_driver_options(c); _add_cap_options(c)
    c.add_argument("--output",default="run/compiled.json")
    c.set_defaults(fn=cmd_compile)

    t=sub.add_parser("test",help="run deterministic convergence/red-team/fuzz suites")
    t.set_defaults(fn=cmd_test)

    args=p.parse_args()
    args.fn(args)

if __name__=="__main__":
    main()
