from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
import json, math, time
from collections import Counter, defaultdict, deque
from typing import Any
from pathlib import Path
import os
from .calibration import report as calibration_report

KEYS={
0:"ACCEPT_GO",1:"ORDERS",2:"STATUS",3:"BLOCKERS",4:"OPTION",5:"APPROVE",
6:"DENY_REPLAN",7:"ANSWER_CORRECT",8:"EXPAND",9:"HALT_RESUME"
}

class HumanTaskClass(str,Enum):
    AUTHORIZATION="AUTHORIZATION"
    SECRET="SECRET"
    PREFERENCE="PREFERENCE"
    PHYSICAL="PHYSICAL"
    IDENTITY="IDENTITY"
    AMBIGUITY="AMBIGUITY"

@dataclass(frozen=True)
class HumanTask:
    id:str
    project:str
    cls:HumanTaskClass
    summary:str
    options:tuple[str,...]=()
    recommendation:int|None=None
    cost_of_wait:float=0.0
    needed_from:str="human"
    readiness_check:str=""
    dependencies:tuple[str,...]=()
    proof_of_attempt:tuple[str,...]=()
    risk:float=0.0
    expires_at:float|None=None
    metadata:dict[str,Any]=field(default_factory=dict)

    def validate(self)->None:
        if self.recommendation is not None and not (0 <= self.recommendation <= 9):
            raise ValueError("recommendation-must-be-key-0-9")
        if self.cls not in {HumanTaskClass.PHYSICAL,HumanTaskClass.IDENTITY} and len(self.proof_of_attempt)<2:
            raise ValueError("human-task-requires-proof-of-attempt")
        if self.risk < 0 or self.risk > 1: raise ValueError("risk-out-of-range")

@dataclass(frozen=True)
class Prediction:
    id:str
    task_id:str
    state_hash:str
    key:int
    probability:float
    distribution:dict[int,float]
    support:int
    ood:float
    made_at:float

@dataclass
class DecisionEvent:
    prediction_id:str
    task_id:str
    state_hash:str
    predicted_key:int
    predicted_p:float
    actual_key:int
    support:int
    ood:float
    risk:float
    human_seconds:float
    correct:bool
    created_at:float
    outcome_verified:bool|None=None
    outcome_value:float|None=None
    receipt_ref:str|None=None
    payload_sha256:str|None=None
    decision_class:str=""
    task_class:str=""

class HumanDecisionLearner:
    """Inspectable online policy learner.

    Hidden predictions are generated before the human answer. The learner uses exact-state
    counts with deterministic backoff. It intentionally does not authorize actions.
    """
    def __init__(self, prior:float=0.5):
        self.prior=float(prior)
        self.counts:dict[str,Counter[int]]=defaultdict(Counter)
        self.events:list[DecisionEvent]=[]
        self.pending:dict[str,Prediction]={}
        self.seen_states:Counter[str]=Counter()
        self.ngrams:dict[int,Counter[tuple[int,...]]]={n:Counter() for n in range(2,9)}
        self.sequence=deque(maxlen=32)

    @staticmethod
    def canonical_state(state:dict[str,Any])->str:
        raw=json.dumps(state,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        return sha256(raw).hexdigest()

    @staticmethod
    def backoff_keys(state:dict[str,Any])->tuple[str,...]:
        exact=HumanDecisionLearner.canonical_state(state)
        project=str(state.get("project","")); cls=str(state.get("class","")); action=str(state.get("action",""))
        risk_bucket=int(float(state.get("risk",0))*4)
        # de-duplicate to avoid the historical HLoop double-counting bug.
        vals=[f"exact:{exact}",f"pa:{project}|{action}",f"ca:{cls}|{action}",f"a:{action}|r:{risk_bucket}",f"a:{action}","global"]
        return tuple(dict.fromkeys(vals))

    def _distribution(self,state:dict[str,Any])->tuple[dict[int,float],int,float]:
        keys=self.backoff_keys(state)
        selected=None
        for k in keys:
            n=sum(self.counts[k].values())
            if n:
                selected=k;break
        c=self.counts[selected] if selected else Counter()
        support=sum(c.values())
        alpha=self.prior
        denom=support+10*alpha
        dist={i:(c[i]+alpha)/denom for i in range(10)}
        exact_n=sum(self.counts[keys[0]].values())
        ood=1.0/(1.0+exact_n)
        return dist,support,ood

    def predict_hidden(self,task:HumanTask,state:dict[str,Any])->Prediction:
        state={**state,"project":task.project,"class":task.cls.value,"risk":task.risk}
        dist,support,ood=self._distribution(state)
        key=max(dist,key=lambda k:(dist[k],-k))
        state_hash=self.canonical_state(state)
        pid="pred:"+sha256(f"{task.id}|{state_hash}|{len(self.pending)}|{time.time_ns()}".encode()).hexdigest()
        p=Prediction(pid,task.id,state_hash,key,dist[key],dist,support,ood,time.time())
        self.pending[pid]=p; self.seen_states[state_hash]+=1
        return p

    def observe(self,prediction_id:str,task:HumanTask,state:dict[str,Any],actual_key:int,human_seconds:float,payload_sha256:str|None=None)->DecisionEvent:
        if prediction_id not in self.pending: raise ValueError("prediction-must-exist-before-answer")
        if actual_key not in KEYS: raise ValueError("key-must-be-0-9")
        pred=self.pending.pop(prediction_id)
        if pred.task_id!=task.id: raise ValueError("prediction-task-mismatch")
        state={**state,"project":task.project,"class":task.cls.value,"risk":task.risk}
        if self.canonical_state(state)!=pred.state_hash: raise ValueError("state-changed-after-prediction")
        # Each distinct backoff bucket is incremented once.
        for k in self.backoff_keys(state): self.counts[k][actual_key]+=1
        dclass=str(state.get("action") or state.get("decision_class") or "generic")
        ev=DecisionEvent(pred.id,task.id,pred.state_hash,pred.key,pred.probability,actual_key,pred.support,pred.ood,task.risk,float(human_seconds),pred.key==actual_key,time.time(),payload_sha256=payload_sha256,decision_class=dclass,task_class=task.cls.value)
        self.events.append(ev)
        self.sequence.append(actual_key)
        seq=list(self.sequence)
        for n in range(2,min(8,len(seq))+1):self.ngrams[n][tuple(seq[-n:])]+=1
        return ev

    def join_outcome(self,prediction_id:str,*,verified:bool,value:float=1.0,receipt_ref:str|None=None)->DecisionEvent:
        for ev in reversed(self.events):
            if ev.prediction_id==prediction_id:
                ev.outcome_verified=bool(verified);ev.outcome_value=float(value);ev.receipt_ref=receipt_ref;return ev
        raise KeyError(prediction_id)

    def metrics(self)->dict[str,float]:
        n=len(self.events)
        if not n:return {"n":0,"accuracy":0.0,"brier":0.0,"human_seconds":0.0,"validated_useful_work":0.0,"autonomy_efficiency":0.0}
        acc=sum(e.correct for e in self.events)/n
        brier=sum((e.predicted_p-(1.0 if e.correct else 0.0))**2 for e in self.events)/n
        hs=sum(e.human_seconds for e in self.events)
        useful=sum((e.outcome_value or 0.0) for e in self.events if e.outcome_verified is True)
        return {"n":n,"accuracy":acc,"brier":brier,"human_seconds":hs,"validated_useful_work":useful,"autonomy_efficiency":useful/max(hs,1e-9)}


    def local_events(self,task:HumanTask,state:dict[str,Any])->list[DecisionEvent]:
        """Events relevant to this decision family. Never borrow confidence from unrelated H-tasks."""
        dclass=str(state.get("action") or state.get("decision_class") or "generic")
        rows=[e for e in self.events if e.decision_class==dclass and e.task_class==task.cls.value]
        return rows

    def local_metrics(self,task:HumanTask,state:dict[str,Any])->dict[str,float]:
        rows=self.local_events(task,state)
        if not rows:return {"n":0,"accuracy":0.0,"brier":1.0,"human_seconds":0.0,"validated_useful_work":0.0}
        n=len(rows);acc=sum(e.correct for e in rows)/n
        brier=sum((e.predicted_p-(1.0 if e.correct else 0.0))**2 for e in rows)/n
        hs=sum(e.human_seconds for e in rows)
        useful=sum((e.outcome_value or 0.0) for e in rows if e.outcome_verified is True)
        return {"n":n,"accuracy":acc,"brier":brier,"human_seconds":hs,"validated_useful_work":useful}

    def macro_candidates(self,min_support:int=3)->list[dict[str,Any]]:
        out=[]
        for n,c in self.ngrams.items():
            for seq,support in c.items():
                if support>=min_support:
                    out.append({"sequence":"".join(map(str,seq)),"keys":[KEYS[x] for x in seq],"support":support,"length":n})
        return sorted(out,key=lambda x:(-x["support"],-x["length"],x["sequence"]))

    def to_dict(self)->dict[str,Any]:
        # Pending hidden predictions are deliberately not persisted: after a restart the system
        # must predict again before it can observe a human answer.
        return {
            "schema":"agentcom.human-policy/0.2",
            "prior":self.prior,
            "counts":{k:{str(i):int(v) for i,v in c.items()} for k,c in self.counts.items()},
            "events":[asdict(e) for e in self.events],
            "seen_states":dict(self.seen_states),
            "ngrams":{str(n):{"".join(map(str,k)):int(v) for k,v in c.items()} for n,c in self.ngrams.items()},
            "sequence":list(self.sequence),
        }

    @classmethod
    def from_dict(cls,data:dict[str,Any])->"HumanDecisionLearner":
        x=cls(float(data.get("prior",0.5)))
        for k,c in (data.get("counts") or {}).items():
            x.counts[k]=Counter({int(i):int(v) for i,v in c.items()})
        x.events=[DecisionEvent(**e) for e in data.get("events",[])]
        x.seen_states=Counter({str(k):int(v) for k,v in (data.get("seen_states") or {}).items()})
        for ns,c in (data.get("ngrams") or {}).items():
            n=int(ns);x.ngrams[n]=Counter({tuple(int(ch) for ch in seq):int(v) for seq,v in c.items()})
        x.sequence=deque((int(v) for v in data.get("sequence",[])),maxlen=32)
        return x

    def save(self,path:str|Path)->None:
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix(p.suffix+".tmp")
        raw=json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(raw)
        os.replace(tmp,p)
        try:os.chmod(p,0o600)
        except OSError:pass

    @classmethod
    def load(cls,path:str|Path)->"HumanDecisionLearner":
        p=Path(path)
        return cls.from_dict(json.loads(p.read_text())) if p.exists() else cls()

@dataclass(frozen=True)
class AutonomyPolicy:
    min_support:int=20
    min_accuracy:float=0.95
    max_brier:float=0.08
    max_ood:float=0.15
    max_risk:float=0.25
    min_verified_outcomes:int=15
    max_failure_rate:float=0.05
    max_failure_upper:float=0.15
    max_ece:float=0.20

class AutonomyGate:
    def __init__(self,policy:AutonomyPolicy|None=None):self.policy=policy or AutonomyPolicy()
    def decide(self,learner:HumanDecisionLearner,pred:Prediction,task:HumanTask)->dict[str,Any]:
        p=self.policy;events=learner.local_events(task,{"action":getattr(pred,"decision_class","")}) if False else None
        # Promotion is local to task class + decision family. The state hash itself can vary,
        # but unrelated human behaviors cannot contribute support/calibration.
        matching=[e for e in learner.events if e.task_class==task.cls.value]
        # Prefer the predicted task's decision family when available through historical rows.
        families=[e.decision_class for e in matching if e.task_id==task.id and e.decision_class]
        if families:
            matching=[e for e in matching if e.decision_class==families[-1]]
        verified=[e for e in matching if e.outcome_verified is not None]
        failures=sum(1 for e in verified if e.outcome_verified is False)
        if matching:
            n=len(matching);acc=sum(e.correct for e in matching)/n
            brier=sum((e.predicted_p-(1.0 if e.correct else 0.0))**2 for e in matching)/n
            metrics={"accuracy":acc,"brier":brier}
        else:
            metrics={"accuracy":0.0,"brier":1.0}
        cal=calibration_report(matching);reasons=[]
        if pred.support<p.min_support:reasons.append("insufficient-support")
        if metrics["accuracy"]<p.min_accuracy:reasons.append("prediction-accuracy")
        if metrics["brier"]>p.max_brier:reasons.append("calibration-brier")
        if cal.ece>p.max_ece:reasons.append("calibration-ece")
        if pred.ood>p.max_ood:reasons.append("ood")
        if task.risk>p.max_risk:reasons.append("risk")
        if len(verified)<p.min_verified_outcomes:reasons.append("verified-outcomes")
        if verified and failures/len(verified)>p.max_failure_rate:reasons.append("failure-rate")
        if verified and cal.verified_failure_upper>p.max_failure_upper:reasons.append("failure-risk-upper")
        # Consequential human tasks never become QP authority just because the human policy is predictable.
        authority_still_required=task.cls in {HumanTaskClass.AUTHORIZATION,HumanTaskClass.IDENTITY,HumanTaskClass.SECRET}
        return {"eligible":not reasons,"reasons":reasons,"predicted_key":pred.key,"authority_still_required":authority_still_required,"calibration":asdict(cal)}

class AutonomyStage(str,Enum):
    HUMAN="HUMAN"
    SHADOW="SHADOW"
    SUGGEST="SUGGEST"
    GUARDED_LOCAL="GUARDED_LOCAL"
    AUTO_LOCAL="AUTO_LOCAL"

@dataclass(frozen=True)
class AutonomyDecision:
    stage:AutonomyStage
    progress:float
    predicted_key:int
    probability:float
    support:int
    eligible:bool
    reasons:tuple[str,...]
    hard_human:bool

class ContinualHumanController:
    """Turns every keypad press into local policy evidence while keeping authority separate."""
    HARD_HUMAN={HumanTaskClass.SECRET,HumanTaskClass.IDENTITY,HumanTaskClass.PHYSICAL,HumanTaskClass.AUTHORIZATION,HumanTaskClass.AMBIGUITY}
    def __init__(self,learner:HumanDecisionLearner|None=None,policy:AutonomyPolicy|None=None):
        self.learner=learner or HumanDecisionLearner();self.policy=policy or AutonomyPolicy();self.auto_failures:Counter[str]=Counter();self.auto_runs:Counter[str]=Counter()

    @staticmethod
    def decision_family(task:HumanTask,state:dict[str,Any])->str:
        return f"{task.cls.value}:{state.get('action') or state.get('decision_class') or 'generic'}"

    def _local_rows(self,task:HumanTask,state:dict[str,Any])->list[DecisionEvent]:
        dc=str(state.get("action") or state.get("decision_class") or "generic")
        return [e for e in self.learner.events if e.task_class==task.cls.value and e.decision_class==dc]

    def assess(self,task:HumanTask,state:dict[str,Any],pred:Prediction)->AutonomyDecision:
        rows=self._local_rows(task,state);verified=[e for e in rows if e.outcome_verified is not None]
        failures=sum(1 for e in verified if e.outcome_verified is False);n=len(rows)
        acc=sum(e.correct for e in rows)/n if n else 0.0
        brier=sum((e.predicted_p-(1.0 if e.correct else 0.0))**2 for e in rows)/n if n else 1.0
        cal=calibration_report(rows);p=self.policy;reasons=[]
        if pred.support<p.min_support:reasons.append("insufficient-support")
        if acc<p.min_accuracy:reasons.append("prediction-accuracy")
        if brier>p.max_brier:reasons.append("calibration-brier")
        if cal.ece>p.max_ece:reasons.append("calibration-ece")
        if pred.ood>p.max_ood:reasons.append("ood")
        if task.risk>p.max_risk:reasons.append("risk")
        if len(verified)<p.min_verified_outcomes:reasons.append("verified-outcomes")
        if verified and failures/len(verified)>p.max_failure_rate:reasons.append("failure-rate")
        if verified and cal.verified_failure_upper>p.max_failure_upper:reasons.append("failure-risk-upper")
        family=self.decision_family(task,state)
        if self.auto_failures[family]>0:reasons.append("autonomous-outcome-failure")
        hard=task.cls in self.HARD_HUMAN
        eligible=not reasons and not hard
        # Progress moves on every press, but is descriptive rather than authority.
        support_progress=min(1.0,pred.support/max(p.min_support,1))
        acc_progress=min(1.0,acc/max(p.min_accuracy,1e-9)) if n else 0.0
        verified_progress=min(1.0,len(verified)/max(p.min_verified_outcomes,1))
        risk_progress=1.0 if task.risk<=p.max_risk else 0.0
        progress=max(0.0,min(1.0,0.40*support_progress+0.30*acc_progress+0.20*verified_progress+0.10*risk_progress))
        if hard:stage=AutonomyStage.HUMAN
        elif eligible:stage=AutonomyStage.AUTO_LOCAL
        elif pred.support<5:stage=AutonomyStage.SHADOW
        elif pred.support<max(10,p.min_support):stage=AutonomyStage.SUGGEST
        else:stage=AutonomyStage.GUARDED_LOCAL
        return AutonomyDecision(stage,progress,pred.key,pred.probability,pred.support,eligible,tuple(reasons),hard)

    def predict(self,task:HumanTask,state:dict[str,Any])->tuple[Prediction,AutonomyDecision]:
        pred=self.learner.predict_hidden(task,state)
        return pred,self.assess(task,state,pred)

    def observe(self,prediction_id:str,task:HumanTask,state:dict[str,Any],key:int,human_seconds:float=0.2,payload_sha256:str|None=None)->DecisionEvent:
        return self.learner.observe(prediction_id,task,state,key,human_seconds,payload_sha256)

    def join_outcome(self,prediction_id:str,verified:bool,value:float=1.0,receipt_ref:str|None=None)->DecisionEvent:
        return self.learner.join_outcome(prediction_id,verified=verified,value=value,receipt_ref=receipt_ref)

    def record_autonomous_outcome(self,task:HumanTask,state:dict[str,Any],*,verified:bool)->dict[str,Any]:
        """Outcome monitor for auto-resolved local decisions. It never becomes a human label."""
        family=self.decision_family(task,state);self.auto_runs[family]+=1
        if not verified:self.auto_failures[family]+=1
        return {"family":family,"runs":self.auto_runs[family],"failures":self.auto_failures[family],"verified":bool(verified)}

class HumanTaskQueue:
    def __init__(self):
        self.tasks:dict[str,HumanTask]={};self.resolved:set[str]=set();self.resolutions:dict[str,str|None]={}
    def add(self,task:HumanTask):task.validate();self.tasks[task.id]=task;return task
    def expired(self,now:float|None=None)->list[HumanTask]:
        now=time.time() if now is None else float(now)
        return sorted([t for t in self.tasks.values() if t.id not in self.resolved and t.expires_at is not None and t.expires_at<now],key=lambda t:t.id)
    def ready(self)->list[HumanTask]:
        now=time.time();out=[]
        for t in self.tasks.values():
            if t.id in self.resolved:continue
            if t.expires_at is not None and t.expires_at<now:continue
            if all(d in self.resolved for d in t.dependencies):out.append(t)
        return sorted(out,key=lambda t:(-t.cost_of_wait,t.id))
    def resolve(self,task_id:str,resolution_ref:str|None=None):
        if task_id not in self.tasks:raise KeyError(task_id)
        self.resolved.add(task_id);self.resolutions[task_id]=resolution_ref
    def blocked_work(self,task_id:str,work_dependencies:dict[str,set[str]])->set[str]:
        return {wid for wid,deps in work_dependencies.items() if task_id in deps}

def classify_human_boundary(description:str)->HumanTaskClass|None:
    s=description.lower()
    if any(x in s for x in ("create account","sign up","kyc","identity verification","passport")):return HumanTaskClass.IDENTITY
    if any(x in s for x in ("password","api key","secret","otp","2fa")):return HumanTaskClass.SECRET
    if any(x in s for x in ("approve spend","authorize","send email","publish","delete","purchase","place order")):return HumanTaskClass.AUTHORIZATION
    if any(x in s for x in ("physically","plug in","scan qr","touch device")):return HumanTaskClass.PHYSICAL
    if any(x in s for x in ("which do you prefer","preference","choose style")):return HumanTaskClass.PREFERENCE
    if any(x in s for x in ("ambiguous","two interpretations","goal unclear")):return HumanTaskClass.AMBIGUITY
    return None
