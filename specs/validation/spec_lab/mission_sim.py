from __future__ import annotations
from dataclasses import asdict
from typing import Any
import json

from .compiler import SpecCompiler
from .drivers import LLMDriver
from .escalation import CapabilityGraph, resolve_block
from .models import ATask, EscalationClaim, ActualityContract, Lane
from .policies import FINAL_POLICY
from .qp_sim import (
    ProbeRegistry, ProbeSpec, make_evidence, settle_claim, mandatory_actuality_true
)
from .scheduler import ready_tasks
from .trajectory import bank_trajectory
from .underengineer import build_minimal_plan, ordered
from .variants import make_lanes

MACHINE_CAPS={
    "filesystem.write","shell","qp","xmr","http","security.scan",
    "deploy.test","github.pr.merge"
}
HUMAN_CAPS={"owner.dns_2fa"}

INDEPENDENT_PROBES={
    "leaf.redeem_once":"provider.entitlement-db",
    "leaf.invocation_readback":"provider.invocation-readback",
    "leaf.xmr_settlement":"xmr.chain-readback",
    "leaf.merchant_entitlement":"provider.entitlement-readback",
    "leaf.deploy_journey":"external.api-journey",
    "leaf.domain":"dns.public-resolver",
    "leaf.github_merge":"github.remote-readback",
}

POLICY_COST={
    "policy.direct":{"token_factor":1.25,"time_factor":1.20,"extra_tokens":10000},
    "policy.reuse_first":{"token_factor":0.75,"time_factor":0.75,"extra_tokens":3000},
    "policy.test_first":{"token_factor":0.90,"time_factor":0.85,"extra_tokens":8000},
    "policy.redteam_first":{"token_factor":1.15,"time_factor":1.05,"extra_tokens":18000},
    "policy.repair_first":{"token_factor":1.00,"time_factor":0.95,"extra_tokens":9000},
}

class SharedArtifactStore:
    def __init__(self):
        self.artifacts: dict[str,Any]={}
        self.human_minutes=0.0
        self.human_requests=0

    def ensure_dns_owner_artifact(self):
        if "owner.dns_2fa" not in self.artifacts:
            self.human_requests += 1
            self.human_minutes += 2.0
            self.artifacts["owner.dns_2fa"]={"session_ref":"opaque:dns-session"}
        return self.artifacts["owner.dns_2fa"]

class SimWorld:
    """Deterministic external world for architecture tests.

    It deliberately contains a few policy-dependent failures so the tournament
    has something real to discriminate. This is a simulation, not a claim that
    GhostCompute itself was built.
    """
    def __init__(self, shared: SharedArtifactStore, *, live: bool):
        self.shared=shared
        self.live=live
        self.attempts: dict[tuple[str,str],int]={}
        self.effects: list[dict[str,Any]]=[]

    def execute_task(self, lane: Lane, task: ATask) -> tuple[bool,dict[str,Any]]:
        key=(lane.policy,task.covers[0])
        n=self.attempts.get(key,0)+1
        self.attempts[key]=n
        leaf=task.covers[0]

        # Inject realistic first-attempt failures for weaker policies.
        if lane.policy=="policy.direct" and leaf in {"leaf.performance","leaf.deploy_journey"} and n==1:
            return False,{"pass":False,"reason":"first-attempt regression","attempt":n}
        if lane.policy=="policy.repair_first" and leaf=="leaf.deploy_journey" and n==1:
            return False,{"pass":False,"reason":"repair after external journey failure","attempt":n}

        if leaf=="leaf.domain":
            if "owner.dns_2fa" not in self.shared.artifacts:
                return False,{"pass":False,"reason":"owner_2fa_required","attempt":n}
            self.effects.append({"kind":"dns.change","lane":lane.id,"live":self.live})
        elif leaf=="leaf.github_merge":
            self.effects.append({"kind":"github.pr.merge","lane":lane.id,"live":self.live})
        elif leaf=="leaf.xmr_settlement":
            self.effects.append({"kind":"xmr.payment","lane":lane.id,"live":self.live})

        return True,{"pass":True,"leaf":leaf,"attempt":n,"route":task.route_id}

def build_probe_registry(contract: ActualityContract) -> ProbeRegistry:
    r=ProbeRegistry()
    for claim in contract.claims:
        if claim.kind!="leaf":
            continue
        probe=INDEPENDENT_PROBES.get(claim.id,f"probe:{claim.id}")
        r.register(ProbeSpec(
            id=probe,
            source_class="external" if claim.id in INDEPENDENT_PROBES else "test",
            channel=probe,
            trusted=True,
            can_independently_readback=claim.id in INDEPENDENT_PROBES,
        ))
    return r

def _judge(_claim, evidence):
    # World observations, not the worker, determine this field in the sim.
    if any(isinstance(e.value,dict) and e.value.get("pass") is False for e in evidence):
        return "FALSE"
    if evidence and all(isinstance(e.value,dict) and e.value.get("pass") is True for e in evidence):
        return "TRUE"
    return "UNKNOWN"

class MissionSimulator:
    def __init__(self, driver: LLMDriver, raw_spec: str):
        self.driver=driver
        self.raw_spec=raw_spec
        self.shared=SharedArtifactStore()

    def compile(self):
        mission,contract=SpecCompiler(self.driver,policy=FINAL_POLICY).compile(self.raw_spec)
        tasks=ordered(build_minimal_plan(
            contract,
            machine_capabilities=MACHINE_CAPS,
            human_capabilities=HUMAN_CAPS,
            policy=FINAL_POLICY,
        ))
        return mission,contract,tasks

    def run_lane(
        self,
        lane: Lane,
        contract: ActualityContract,
        base_tasks: list[ATask],
        *,
        max_rounds: int = 20,
        live: bool = False,
    ) -> dict[str,Any]:
        # Each lane gets isolated mission/task state but shares true external
        # human artifacts such as owner approval.
        tasks=[ATask(**asdict(t)) for t in base_tasks]
        shared = self.shared if live else SharedArtifactStore()
        world=SimWorld(shared, live=live)
        registry=build_probe_registry(contract)
        leaf_results={}
        proof_ids=[]
        failures=[]
        attempts=0
        model_tokens=0
        model_cost=0.0
        wall=0.0
        htask_ids=[]
        pending_domain=False

        # BLOCKED_CLAIMED routes become certified escalation requests before run.
        for task in tasks:
            if task.state=="BLOCKED_CLAIMED":
                claim=EscalationClaim(
                    parent_atask_id=task.id,
                    blocking_operation_id="dns.change",
                    requirement=(task.capabilities[0] if task.capabilities else "owner.dns_2fa"),
                    blocker_class="owner_reserved",
                    evidence_ids=["capability:missing"],
                    alternatives_checked=[
                        {"route":"dns.api","status":"UNAVAILABLE"},
                        {"route":"delegation","status":"FAILED"},
                    ],
                )
                resolution=resolve_block(
                    claim,
                    CapabilityGraph(machine=MACHINE_CAPS,human=HUMAN_CAPS,authorized=MACHINE_CAPS),
                    attempt_evidence=[],
                    max_cost_usd=0,
                    policy=FINAL_POLICY,
                )
                if resolution.outcome=="H_TASK":
                    task.state="WAITING_H"
                    htask_ids.append(f"h:{task.id}")
                    pending_domain=True
                else:
                    failures.append(f"block-resolution:{task.id}:{resolution.outcome}")
                    task.state="FAILED"

        for round_no in range(max_rounds):
            # After at least one autonomous scheduling round, simulate the
            # principal completing the one certified DNS task. This tests that
            # unrelated work was able to proceed first.
            if pending_domain and round_no>=1:
                if live:
                    shared.ensure_dns_owner_artifact()
                else:
                    # Replayable world supplies the artifact as simulated world
                    # state. It must not consume real operator attention.
                    shared.artifacts["owner.dns_2fa"]={"session_ref":"shadow:dns-session"}
                for task in tasks:
                    if task.state=="WAITING_H":
                        task.state="READY"
                pending_domain=False

            ready=ready_tasks(tasks,policy=FINAL_POLICY)

            # Merge is a consequence after every other leaf has settled TRUE.
            nonmerge_incomplete=[
                t for t in tasks
                if "leaf.github_merge" not in t.covers and t.state!="DONE"
            ]
            ready=[
                t for t in ready
                if "leaf.github_merge" not in t.covers or not nonmerge_incomplete
            ]

            if not ready:
                if all(t.state in {"DONE","FAILED"} for t in tasks):
                    break
                continue

            for task in ready:
                task.state="RUNNING"
                attempts+=1
                profile=POLICY_COST.get(lane.policy,POLICY_COST["policy.direct"])
                tokens=int((1500+200*task.complexity)*profile["token_factor"])
                model_tokens+=tokens
                model_cost+=tokens/1_000_000*0.80
                wall+=max(0.25,float(task.wall_minutes or 1))*profile["time_factor"]

                success,obs=world.execute_task(lane,task)
                leaf=task.covers[0]
                probe=INDEPENDENT_PROBES.get(leaf,f"probe:{leaf}")
                evidence=make_evidence(
                    leaf,probe_id=probe,value=obs,
                    observed_at="2026-09-14T12:00:00Z",
                    source_class="external" if leaf in INDEPENDENT_PROBES else "test",
                    independent=leaf in INDEPENDENT_PROBES,
                    environment_root="sha256:sim-world-v1",
                )
                receipt=settle_claim(
                    contract,leaf,[evidence],
                    now="2026-09-14T12:00:01Z",
                    judge=_judge,
                    evaluator_root=next(iter(contract.evaluator_roots.values()),None),
                    probe_registry=registry,
                    policy=FINAL_POLICY,
                )
                leaf_results[leaf]=receipt.result
                proof_ids.append(receipt.id)

                if receipt.result=="TRUE":
                    task.state="DONE"
                else:
                    failures.append(f"{leaf}:attempt-{obs.get('attempt')}:{receipt.result}")
                    # bounded retry in the simulator
                    if world.attempts[(lane.policy,leaf)] < 2:
                        task.state="READY"
                    else:
                        task.state="FAILED"

        actuality=mandatory_actuality_true(contract,leaf_results)
        profile=POLICY_COST.get(lane.policy,POLICY_COST["policy.direct"])
        model_tokens+=profile["extra_tokens"]
        model_cost+=profile["extra_tokens"]/1_000_000*0.80
        metrics={
            # Human owner artifact is mission-global; do not charge later lanes
            # differently based on tournament order.
            "human_minutes":0.0,
            "cost_usd":round(model_cost,6),
            "wall_minutes":round(wall,3),
            "tokens":model_tokens,
            "attempts":attempts,
            "complexity":sum(t.complexity for t in tasks),
        }
        lane.actuality=actuality
        lane.qp_valid=actuality and all(t.state=="DONE" for t in tasks)
        lane.authority_violations=0
        lane.metrics=metrics
        lane.status="VALID" if lane.qp_valid else "INVALID"

        trajectory=bank_trajectory(
            contract_root=contract.contract_root,
            lane_id=lane.id,
            proof_ids=proof_ids,
            route_ids=[t.route_id for t in tasks],
            failures=failures,
            metrics=metrics,
            verified=lane.qp_valid,
        )
        return {
            "lane":asdict(lane),
            "tasks":[asdict(t) for t in tasks],
            "leaf_results":leaf_results,
            "failures":failures,
            "proof_ids":proof_ids,
            "effects":world.effects,
            "htasks":htask_ids,
            "trajectory":asdict(trajectory),
            "validation_class":"LIVE" if live else "SHADOW_WORLD",
            "live_effect_count":sum(1 for e in world.effects if e.get("live")),
        }

    def run_tournament(self, *, variants: int = 5) -> dict[str,Any]:
        mission,contract,tasks=self.compile()
        evaluator_root=next(iter(contract.evaluator_roots.values()),"sha256:evaluator")
        lanes=make_lanes(
            contract.contract_root,
            count=variants,
            mission_budget_usd=float(mission.budget.get("usd",0)),
            evaluator_root=evaluator_root,
            policy=FINAL_POLICY,
        )

        # Stage 1: every candidate runs in a replayable shadow world.
        shadow_results=[self.run_lane(l,contract,tasks,live=False) for l in lanes]
        from .variants import rank_lanes
        ranked=rank_lanes(lanes,policy=FINAL_POLICY)
        winner=ranked[0] if ranked else None

        # Stage 2: only the promoted candidate receives the live consequence belt.
        live_result=None
        if winner is not None:
            live_lane=Lane(
                id=f"live-{winner.policy}",
                contract_root=winner.contract_root,
                policy=winner.policy,
                budget={"usd":float(mission.budget.get("usd",0))},
                evaluator_root=winner.evaluator_root,
                status="PROMOTED",
            )
            live_result=self.run_lane(live_lane,contract,tasks,live=True)

        return {
            "mission":asdict(mission),
            "contract_root":contract.contract_root,
            "base_plan":[asdict(t) for t in tasks],
            "shadow_lanes":shadow_results,
            "ranking":[x.id for x in ranked],
            "winner":winner.id if winner else None,
            "winner_policy":winner.policy if winner else None,
            "live_run":live_result,
            "mission_human":{
                "requests":self.shared.human_requests,
                "minutes":self.shared.human_minutes,
                "artifacts":list(self.shared.artifacts),
            },
            "live_effect_count":0 if live_result is None else live_result["live_effect_count"],
        }
