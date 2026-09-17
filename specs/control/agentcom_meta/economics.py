from __future__ import annotations
from dataclasses import dataclass,field
from math import log,sqrt
from typing import Any

@dataclass(frozen=True)
class ModelRoute:
    id:str
    provider:str
    model:str
    input_per_million:float
    output_per_million:float
    cached_input_per_million:float=0.0
    context:int=0
    quality:float=0.5
    latency_s:float=5.0
    free:bool=False
    provenance:tuple[str,...]=()

@dataclass(frozen=True)
class TaskEconomics:
    task_family:str
    proof_class:str="Q2"
    input_tokens:int=4000
    output_tokens:int=1500
    cached_input_tokens:int=0
    min_context:int=0
    min_quality:float=0.0
    verification_cost:float=0.0
    repair_cost_if_failure:float=0.0
    orchestration_cost:float=0.0
    latency_value_per_second:float=0.0
    human_value_per_second:float=0.0
    max_money:float|None=None
    risk:float=0.0

@dataclass
class RouteStats:
    successes:int=0
    failures:int=0
    total_cost:float=0.0
    total_latency:float=0.0
    alpha0:float=1.0
    beta0:float=1.0
    @property
    def n(self):return self.successes+self.failures
    @property
    def p_success(self):return (self.alpha0+self.successes)/(self.alpha0+self.beta0+self.n)
    def update(self,ok:bool,cost:float,latency:float):
        self.successes+=int(ok);self.failures+=int(not ok);self.total_cost+=float(cost);self.total_latency+=float(latency)

class LiveLLMAdapter:
    """Normalize LiveLLM-like market payloads without trusting them as proof."""
    @staticmethod
    def routes(payload:dict[str,Any])->list[ModelRoute]:
        items=payload.get("models") or payload.get("routes") or payload.get("items") or []
        out=[]
        for x in items:
            econ=x.get("economics",x.get("pricing",{}));caps=x.get("capabilities",{})
            iid=x.get("id") or x.get("route_id") or x.get("model")
            if not iid:continue
            out.append(ModelRoute(
                id=str(iid),provider=str(x.get("provider","unknown")),model=str(x.get("model",iid)),
                input_per_million=float(econ.get("input_per_million",econ.get("input",0.0)) or 0.0),
                output_per_million=float(econ.get("output_per_million",econ.get("output",0.0)) or 0.0),
                cached_input_per_million=float(econ.get("cached_input_per_million",econ.get("cached_input",0.0)) or 0.0),
                context=int(caps.get("context",x.get("context",0)) or 0),quality=float(x.get("quality",0.5)),
                latency_s=float(x.get("latency_s",5.0)),free=bool(x.get("free",False)),
                provenance=tuple(x.get("evidence_ids",x.get("provenance",[])) or [])))
        return out

def attempt_cost(route:ModelRoute,task:TaskEconomics)->float:
    return (task.input_tokens/1e6*route.input_per_million + task.output_tokens/1e6*route.output_per_million + task.cached_input_tokens/1e6*route.cached_input_per_million)

def expected_cost_to_verified_completion(route:ModelRoute,task:TaskEconomics,stats:RouteStats)->float:
    """QDW semantics: base + expected retry + expected repair + verification + orchestration.

    We do not divide the whole quantity by p after retry/repair are already expected.
    Under a geometric retry model E[retry attempts]=(1-p)/p.
    """
    p=max(min(stats.p_success,0.999999),1e-6);base=attempt_cost(route,task)
    expected_retry=base*(1-p)/p
    expected_repair=task.repair_cost_if_failure*(1-p)
    latency=(route.latency_s/p)*task.latency_value_per_second
    return base+expected_retry+expected_repair+task.verification_cost+task.orchestration_cost+latency

class QDWModelRouter:
    def __init__(self):self.stats:dict[tuple[str,str,str],RouteStats]={}
    def stat(self,family:str,route_id:str,proof_class:str="*")->RouteStats:
        return self.stats.setdefault((family,proof_class,route_id),RouteStats())
    def record(self,family:str,route_id:str,*,ok:bool,cost:float,latency:float,proof_class:str="*"):
        self.stat(family,route_id,proof_class).update(ok,cost,latency)
    def _evidence_stat(self,task:TaskEconomics,route_id:str)->RouteStats:
        specific=self.stats.get((task.task_family,task.proof_class,route_id))
        if specific is not None and specific.n:
            return specific
        # Backward-compatible aggregate prior; never overwrites proof-class-specific evidence.
        return self.stats.get((task.task_family,"*",route_id),RouteStats())
    def rank(self,routes:list[ModelRoute],task:TaskEconomics,*,exploration:float=0.0)->list[dict[str,Any]]:
        rows=[]
        for r in routes:
            if r.context<task.min_context or r.quality<task.min_quality:continue
            s=self._evidence_stat(task,r.id);cost=expected_cost_to_verified_completion(r,task,s)
            if task.max_money is not None and cost>task.max_money:continue
            # Lower score is better. UCB-like exploration bonus rewards under-sampled routes only when explicitly requested.
            bonus=exploration*sqrt(log(2+sum(x.n for x in self.stats.values()))/(1+s.n))
            risk_penalty=task.risk*(1-s.p_success)
            score=cost+risk_penalty-bonus
            rows.append({"route":r,"score":score,"expected_cost_verified":cost,"p_success":s.p_success,"n":s.n,"exploration_bonus":bonus})
        return sorted(rows,key=lambda x:(x["score"],-x["route"].quality,x["route"].id))
    def choose(self,routes:list[ModelRoute],task:TaskEconomics,*,exploration:float=0.0)->dict[str,Any]:
        ranked=self.rank(routes,task,exploration=exploration)
        if not ranked:raise ValueError("no-model-route-satisfies-task")
        return ranked[0]

@dataclass(frozen=True)
class GoalAwareBudget:
    campaign_money:float
    exploration_fraction:float=0.2
    high_proof_multiplier:float=1.5
    def allocation(self,proof_class:str,priority:float,uncertainty:float)->dict[str,float]:
        q=int(str(proof_class).lstrip("Q") or 0);w=max(priority,0.01)*(1+self.high_proof_multiplier*max(q-4,0)/4)*(1+uncertainty)
        # This is a cap proposal, never authority to spend.
        exploit=self.campaign_money*(1-self.exploration_fraction);explore=self.campaign_money*self.exploration_fraction
        return {"exploit_cap":min(self.campaign_money,exploit*w/(1+w)),"explore_cap":min(self.campaign_money,explore*w/(1+w)),"weight":w}


@dataclass(frozen=True)
class EconomicPlan:
    route_id:str
    model:str
    provider:str
    expected_cost_verified:float
    p_success:float
    exploit_cap:float
    explore_cap:float
    proof_class:str
    task_family:str
    requires_qp_spend_grant:bool
    provenance:tuple[str,...]

class EconomicController:
    """Compose market observations, QDW routing and GAB caps into a non-authorizing proposal."""
    def __init__(self,router:QDWModelRouter|None=None):self.router=router or QDWModelRouter()
    def plan(self,routes:list[ModelRoute],task:TaskEconomics,*,campaign_money:float,priority:float=1.0,uncertainty:float=0.0,exploration_lane:bool=False)->EconomicPlan:
        gab=GoalAwareBudget(campaign_money).allocation(task.proof_class,priority,uncertainty)
        picked=self.router.choose(routes,task,exploration=(0.15 if exploration_lane else 0.0))
        r=picked["route"]
        return EconomicPlan(r.id,r.model,r.provider,float(picked["expected_cost_verified"]),float(picked["p_success"]),float(gab["exploit_cap"]),float(gab["explore_cap"]),task.proof_class,task.task_family,not r.free,tuple(r.provenance))
