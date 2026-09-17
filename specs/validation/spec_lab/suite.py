from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any
import json

from .budget import BudgetLedger
from .canonical import digest
from .compiler import SpecCompiler
from .drivers import RecordedDriver, TransformDriver
from .effects import EffectJournal, InjectedCrash
from .escalation import CapabilityGraph, resolve_block
from .models import ActualityContract, Claim, ATask, EscalationClaim, Lane
from .policies import KernelPolicy, FINAL_POLICY
from .qp_sim import make_evidence, settle_claim, mandatory_actuality_true, QPError
from .scheduler import ready_tasks
from .trajectory import bank_trajectory, compare
from .underengineer import build_minimal_plan, ordered
from .validation import ContractError, reject_orphan_tasks
from .variants import make_lanes, rank_lanes

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PACKAGE_ROOT / "specs" / "ghostcompute_long_spec.md"
ORACLE_PATH = PACKAGE_ROOT / "fixtures" / "oracle_ghostcompute.json"

MACHINE_CAPS = {
    "filesystem.write","shell","qp","xmr","http","security.scan",
    "deploy.test","github.pr.merge"
}
HUMAN_CAPS = {"owner.dns_2fa"}

def _base():
    return SPEC_PATH.read_text(), json.loads(ORACLE_PATH.read_text())

def _compile(policy: KernelPolicy, driver=None):
    spec, oracle = _base()
    driver = driver or RecordedDriver(oracle)
    return SpecCompiler(driver, policy=policy).compile(spec)

def _custom_contract(claim: Claim) -> ActualityContract:
    body={
        "mission_root":"sha256:mission",
        "claims":[asdict(claim)],
        "evaluator_roots":{"x":"sha256:evaluator"},
        "environment":{},
    }
    return ActualityContract(
        mission_root=body["mission_root"],
        claims=[claim],
        evaluator_roots=body["evaluator_roots"],
        environment={},
        contract_root=digest("actuality-contract",body),
    )

def case_claim_first(policy):
    try:
        _, c=_compile(policy)
        mandatory=[x for x in c.claims if x.kind=="leaf" and x.mandatory]
        ok=bool(mandatory) and all(x.proof_id for x in mandatory)
        return ok, f"{len(mandatory)} mandatory leaves, proof-bound={ok}"
    except Exception as e:
        return False, repr(e)

def case_non_goals_not_mandatory(policy):
    try:
        m,_=_compile(policy)
        bad=[x for x in m.mandatory_outcomes if any(str(ng).lower() in x["statement"].lower() for ng in m.non_goals)]
        optional=[x for x in m.mandatory_outcomes if x["id"].startswith("optional_")]
        ok=not bad and not optional
        return ok, f"non_goal_collisions={len(bad)} optional_leaks={len(optional)}"
    except Exception as e:
        return False, repr(e)

def case_driver_optional_misclassification(policy):
    spec, oracle=_base()
    def mutate(out):
        x=json.loads(json.dumps(out))
        idea=x["optional_ideas"][0]
        x["mandatory_outcomes"].append({
            "id":"bad_optional_ui",
            "statement":idea,
            "source_refs":["§16"]
        })
        return x
    d=TransformDriver(RecordedDriver(oracle),{"mission":mutate})
    try:
        m,_=SpecCompiler(d,policy=policy).compile(spec)
        bad=any(x["id"]=="bad_optional_ui" for x in m.mandatory_outcomes)
        return (not bad), "compiler accepted LLM optional→mandatory drift" if bad else "drift rejected"
    except ContractError as e:
        return True, f"rejected: {e}"
    except Exception as e:
        return False, repr(e)

def case_traceability(policy):
    spec, oracle=_base()
    def mutate(out):
        x=json.loads(json.dumps(out))
        for c in x["claims"]:
            if c["kind"]=="leaf" and c["mandatory"]:
                c["source_refs"]=[]
                break
        return x
    d=TransformDriver(RecordedDriver(oracle),{"claims":mutate})
    try:
        SpecCompiler(d,policy=policy).compile(spec)
        return (not policy.require_traceability), "missing source ref accepted"
    except ContractError:
        return policy.require_traceability, "missing source ref rejected"

def case_missing_proof(policy):
    spec, oracle=_base()
    def mutate(out):
        x=json.loads(json.dumps(out))
        for c in x["claims"]:
            if c["kind"]=="leaf" and c["mandatory"]:
                c["proof_id"]=None
                break
        return x
    d=TransformDriver(RecordedDriver(oracle),{"claims":mutate})
    try:
        SpecCompiler(d,policy=policy).compile(spec)
        return (not policy.require_proofs), "missing proof binding accepted"
    except ContractError:
        return policy.require_proofs, "missing proof binding rejected"

def case_underengineer_reuse(policy):
    try:
        _, c=_compile(policy)
        tasks=build_minimal_plan(
            c,machine_capabilities=MACHINE_CAPS,human_capabilities=HUMAN_CAPS,policy=policy
        )
        route={t.covers[0]:t.route_id for t in tasks}
        ok=(
            route.get("leaf.xmr_settlement")=="reuse-xmr-payment-module"
            and route.get("leaf.infer")=="deterministic-local-transform"
            and route.get("leaf.performance")=="run-local-k6-lite"
        )
        return ok, json.dumps({k:route.get(k) for k in ("leaf.xmr_settlement","leaf.infer","leaf.performance")})
    except Exception as e:
        return False, repr(e)

def case_stop_when_true(policy):
    claim=Claim(
        id="leaf.done",statement="already established",kind="leaf",mandatory=True,
        proof_id="demo",proof_class="external_readback",source_refs=["§x"],
        state="TRUE",routes=[{"id":"build-more","kind":"BUILD","cost_usd":1,"capabilities":[]}],
    )
    c=_custom_contract(claim)
    tasks=build_minimal_plan(c,policy=policy)
    ok=(len(tasks)==0)
    return ok, f"generated_tasks={len(tasks)}"

def case_certified_h_task(policy):
    claim=EscalationClaim(
        parent_atask_id="a:dns",blocking_operation_id="dns.change",
        requirement="owner.dns_2fa",blocker_class="human",
        evidence_ids=["attempt:403"],
        alternatives_checked=[
            {"route":"dns.api","status":"UNAVAILABLE"},
            {"route":"delegation","status":"FAILED"},
        ],
    )
    # Deliberately say machine can do it. A model declaration "human" must not
    # override the runtime capability graph.
    graph=CapabilityGraph(
        machine={"owner.dns_2fa"},human={"owner.dns_2fa"},authorized={"owner.dns_2fa"}
    )
    r=resolve_block(claim,graph,attempt_evidence=["attempt:403"],policy=policy)
    ok=r.outcome!="H_TASK"
    return ok, f"outcome={r.outcome} reason={r.reason}"

def case_real_h_task(policy):
    claim=EscalationClaim(
        parent_atask_id="a:dns",blocking_operation_id="dns.change",
        requirement="owner.dns_2fa",blocker_class="owner_reserved",
        evidence_ids=["attempt:no-session"],
        alternatives_checked=[
            {"route":"dns.api","status":"UNAVAILABLE"},
            {"route":"delegation","status":"FAILED"},
        ],
    )
    graph=CapabilityGraph(machine=set(),human={"owner.dns_2fa"},authorized=set())
    r=resolve_block(claim,graph,attempt_evidence=[],policy=policy)
    ok=r.outcome=="H_TASK"
    return ok, f"outcome={r.outcome}"

def case_m_task_gain(policy):
    base=dict(
        parent_atask_id="a:perf",blocking_operation_id="perf.run",
        requirement="compute.paid",blocker_class="money",
        evidence_ids=["attempt:slow"],
        alternatives_checked=[{"route":"local","status":"FAILED"}],
    )
    graph=CapabilityGraph(machine={"compute.paid"},human=set(),authorized=set())
    no=resolve_block(EscalationClaim(**base,requested_cost_usd=2,estimated_gain=0),graph,
                     attempt_evidence=["attempt:slow"],max_cost_usd=2,policy=policy)
    yes=resolve_block(EscalationClaim(**base,requested_cost_usd=2,estimated_gain=.5),graph,
                      attempt_evidence=["attempt:slow"],max_cost_usd=2,policy=policy)
    ok=no.outcome!="M_TASK" and yes.outcome=="M_TASK"
    return ok, f"zero_gain={no.outcome} positive_gain={yes.outcome}"

def case_non_interference(policy):
    tasks=[
        ATask("a1",["l1"],"x","r",state="READY"),
        ATask("a2",["l2"],"x","r",state="WAITING_H"),
        ATask("a3",["l3"],"x","r",state="READY",blocked_by=["a2"]),
        ATask("a4",["l4"],"x","r",state="READY"),
    ]
    got=[t.id for t in ready_tasks(tasks,policy=policy)]
    ok=set(got)=={"a1","a4"}
    return ok, f"ready={got}"

def case_shared_lane_budget(policy):
    lanes=make_lanes("contract:1",count=5,mission_budget_usd=20,evaluator_root="eval:1",policy=policy)
    total=sum(float(x.budget["usd"]) for x in lanes)
    ok=all(float(x.budget["usd"])<=2 for x in lanes) and total<=10
    return ok, f"lane_budgets={[x.budget['usd'] for x in lanes]} total={total}"

def case_independent_readback(policy):
    claim=Claim(
        id="leaf.buy",statement="purchase really happened",kind="leaf",mandatory=True,
        proof_id="payment",proof_class="independent_readback",
        independent_readback_required=True,source_refs=["§x"]
    )
    c=_custom_contract(claim)
    e=make_evidence("leaf.buy",probe_id="same-channel",value={"ok":True},
                    observed_at="2026-09-14T12:00:00Z",independent=False)
    r=settle_claim(c,"leaf.buy",[e],now="2026-09-14T12:00:01Z",policy=policy)
    ok=r.result=="UNKNOWN"
    return ok, f"result={r.result}"

def case_self_reported_done(policy):
    claim=Claim(
        id="leaf.done",statement="deployed",kind="leaf",mandatory=True,
        proof_id="deploy.health",proof_class="external_readback",source_refs=["§x"]
    )
    c=_custom_contract(claim)
    r=settle_claim(c,"leaf.done",[],now="2026-09-14T12:00:00Z",policy=policy)
    return r.result=="UNKNOWN", f"result={r.result}"

def case_evaluator_immutable(policy):
    lanes=make_lanes("contract",count=2,mission_budget_usd=10,evaluator_root="eval:frozen",policy=policy)
    lanes[0].actuality=lanes[0].qp_valid=True
    lanes[0].metrics={"cost_usd":5}
    lanes[1].actuality=lanes[1].qp_valid=True
    lanes[1].metrics={"cost_usd":1}
    lanes[1].evaluator_root="eval:weakened"
    ranked=rank_lanes(lanes,policy=policy)
    ok=[x.id for x in ranked]==["lane-1"]
    return ok, f"ranked={[x.id for x in ranked]}"

def case_invalid_lane_cannot_win(policy):
    lanes=make_lanes("contract",count=2,mission_budget_usd=10,evaluator_root="eval",policy=policy)
    lanes[0].actuality=True;lanes[0].qp_valid=True;lanes[0].metrics={"cost_usd":2}
    lanes[1].actuality=False;lanes[1].qp_valid=True;lanes[1].metrics={"cost_usd":0.01}
    ranked=rank_lanes(lanes,policy=policy)
    ok=[x.id for x in ranked]==["lane-1"]
    return ok, f"ranked={[x.id for x in ranked]}"

def case_unknown_cost(policy):
    claim=Claim(
        id="leaf.unknowncost",statement="route",kind="leaf",mandatory=True,
        proof_id="demo",proof_class="external_readback",source_refs=["§x"],
        routes=[{"id":"mystery","kind":"INTEGRATE","cost_usd":None,"time_minutes":1,"capabilities":[]}]
    )
    c=_custom_contract(claim)
    tasks=build_minimal_plan(c,policy=policy)
    value=tasks[0].cost_usd
    ok=value is None
    return ok, f"cost_usd={value!r}"

def case_secret_rejection(policy):
    spec, oracle=_base()
    poisoned=spec+"\n\nDeployment note: API_KEY=sk-THIS_SHOULD_NEVER_ENTER_CONTEXT_1234567890"
    try:
        SpecCompiler(RecordedDriver(oracle),policy=policy).compile(poisoned)
        return False, "secret-like string accepted"
    except ContractError:
        return True, "secret-like string rejected"

def case_material_ambiguity(policy):
    spec, oracle=_base()
    def mutate(out):
        x=json.loads(json.dumps(out))
        x["ambiguities"].append({
            "id":"payment_semantics",
            "question":"Does simulation count or must it be stagenet?",
            "affects_acceptance":True,
        })
        return x
    try:
        SpecCompiler(TransformDriver(RecordedDriver(oracle),{"mission":mutate}),policy=policy).compile(spec)
        return False, "material ambiguity silently frozen"
    except ContractError:
        return True, "material ambiguity blocked"

def case_idempotent_crash_recovery(policy):
    journal=EffectJournal()
    action={"capability":"github.pr.merge","pr":17}
    try:
        journal.execute(action=action,idempotency_key="k1",crash_at="after_commit",policy=policy)
    except InjectedCrash:
        pass
    journal.execute(action=action,idempotency_key="k1",policy=policy)
    ok=journal.physical_effect_count==1
    return ok, f"physical_effect_count={journal.physical_effect_count}"

def case_budget_refusal(policy):
    b=BudgetLedger({"usd":1})
    a=b.record({"usd":.4})
    c=b.record({"usd":.7})
    ok=a[0] and not c[0] and b.used["usd"]==.4
    return ok, f"first={a} crossing={c} used={b.used['usd']}"

def case_root_actuality(policy):
    root=Claim("root.x","x","root",True,depends_on=["leaf.a","leaf.b"],source_refs=["§x"])
    a=Claim("leaf.a","a","leaf",True,proof_id="x",proof_class="external_readback",source_refs=["§x"])
    b=Claim("leaf.b","b","leaf",True,proof_id="x",proof_class="external_readback",source_refs=["§x"])
    body={"mission_root":"m","claims":[asdict(root),asdict(a),asdict(b)],"evaluator_roots":{},"environment":{}}
    c=ActualityContract("m",[root,a,b],{}, {}, digest("actuality-contract",body))
    ok1=mandatory_actuality_true(c,{"leaf.a":"TRUE","leaf.b":"TRUE"})
    ok2=mandatory_actuality_true(c,{"leaf.a":"TRUE","leaf.b":"UNKNOWN"})
    return ok1 and not ok2, f"all_true={ok1} unknown_blocks={not ok2}"

def case_trajectory_improvement(policy):
    a=bank_trajectory(
        contract_root="c",lane_id="a",proof_ids=["p1"],route_ids=["r1"],
        failures=[],metrics={"human_minutes":2,"cost_usd":2,"wall_minutes":30,"tokens":1000,"attempts":3,"complexity":3},
        verified=True,
    )
    b=bank_trajectory(
        contract_root="c",lane_id="b",proof_ids=["p2"],route_ids=["r2"],
        failures=[],metrics={"human_minutes":1,"cost_usd":1.5,"wall_minutes":20,"tokens":800,"attempts":2,"complexity":2},
        verified=True,
    )
    d=compare(a,b)
    return d["improved"], json.dumps(d)

CASES: list[tuple[str,str,Callable[[KernelPolicy],tuple[bool,str]]]] = [
    ("claim_first","Spec compiles into proof-bound observable leaves before tasks",case_claim_first),
    ("non_goals","Explicit non-goals/optional ideas never become production scope",case_non_goals_not_mandatory),
    ("llm_optional_drift","Validator catches an LLM that reclassifies an optional idea as mandatory",case_driver_optional_misclassification),
    ("traceability","Mandatory claims remain grounded to source refs",case_traceability),
    ("proof_binding","Mandatory leaves cannot exist without proof semantics",case_missing_proof),
    ("underengineer","Minimum proof path reuses existing primitives before building/buying",case_underengineer_reuse),
    ("stop_rule","No synthetic work after leaf is already TRUE",case_stop_when_true),
    ("certified_h","Model cannot declare a human blocker against runtime capability facts",case_certified_h_task),
    ("real_h","A genuine owner-reserved blocker promotes to H-Task",case_real_h_task),
    ("marginal_m","Money escalation requires bounded positive marginal gain",case_m_task_gain),
    ("non_interference","One H blocker does not stall unrelated READY work",case_non_interference),
    ("lane_budget","Variants share mission budget rather than multiplying it",case_shared_lane_budget),
    ("readback","Consequential claim needs independent readback",case_independent_readback),
    ("no_self_done","Worker narrative without evidence cannot settle Actuality",case_self_reported_done),
    ("frozen_evaluator","Candidate cannot win by changing evaluator",case_evaluator_immutable),
    ("invalid_lane","Cheap invalid lane cannot outrank valid lane",case_invalid_lane_cannot_win),
    ("unknown_cost","Unknown provider cost stays UNKNOWN, never zero-by-guess",case_unknown_cost),
    ("secret_boundary","Secret-like material rejected from spec/context",case_secret_rejection),
    ("ambiguity_gate","Material acceptance ambiguity blocks contract freeze",case_material_ambiguity),
    ("idempotency","Crash after external commit does not duplicate effect on resume",case_idempotent_crash_recovery),
    ("budget_refusal","Hard budget refuses crossing call without recording it",case_budget_refusal),
    ("unknown_blocks","Mandatory root remains unresolved while a leaf is UNKNOWN",case_root_actuality),
    ("second_run","Verified equivalent second run can prove resource improvement",case_trajectory_improvement),
]

def run_suite(policy: KernelPolicy) -> dict[str, Any]:
    rows=[]
    for test_id,hypothesis,fn in CASES:
        try:
            ok,detail=fn(policy)
        except Exception as e:
            ok,detail=False,f"uncaught {type(e).__name__}: {e}"
        rows.append({
            "id":test_id,
            "hypothesis":hypothesis,
            "pass":bool(ok),
            "detail":detail,
        })
    passed=sum(1 for x in rows if x["pass"])
    return {
        "policy":policy.name,
        "passed":passed,
        "failed":len(rows)-passed,
        "total":len(rows),
        "rows":rows,
    }
