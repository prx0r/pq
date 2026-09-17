from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib,json
from .model import HLoopPolicyModel, HumanContext, HumanDecision, DEFAULT_ACTIONS
from .queue import HumanQueue
from .artifacts import ArtifactVault

@dataclass(frozen=True)
class HLoopEvent:
    id:str
    event_type:str
    task_id:str
    at:str
    body:dict

def _event(event_type,task_id,body):
    at=datetime.now(timezone.utc).isoformat()
    raw={"event_type":event_type,"task_id":task_id,"at":at,"body":body}
    eid="hloop:"+hashlib.sha256(json.dumps(raw,sort_keys=True,default=str).encode()).hexdigest()
    return HLoopEvent(eid,event_type,task_id,at,body)

class HLoopController:
    def __init__(self,queue:HumanQueue,model:HLoopPolicyModel,vault:ArtifactVault):
        self.queue=queue;self.model=model;self.vault=vault
        self.events=[]

    def present(self,task_id:str,ctx:HumanContext):
        task=self.queue.get(task_id)
        if task.state!="OPEN":
            raise ValueError("task not open for a new human decision")
        pred=self.model.predict(ctx)
        event=_event("PREDICTION_BEFORE_HUMAN",task_id,{
            "prediction":asdict(pred),
            "task_payload_hash":task.payload_hash(),
        })
        self.events.append(event)
        task.prediction_ref=event.id
        return pred

    def decide(
        self,task_id:str,ctx:HumanContext,*,digit:int,text:str|None=None,
        artifacts:list[tuple[str,str|bytes,bool,dict]]|None=None,
        external_artifact_ref:str|None=None,
    ):
        task=self.queue.get(task_id)
        if not task.prediction_ref:
            raise ValueError("must call present() and bank hidden prediction before answer")
        pred_event=next(x for x in self.events if x.id==task.prediction_ref)
        p=pred_event.body["prediction"]
        # Rehydrate only fields required by model.update.
        from .model import HumanPrediction
        pred=HumanPrediction(
            predicted_digit=p["predicted_digit"],
            probabilities=tuple(p["probabilities"]),
            confidence=p["confidence"],entropy=p["entropy"],
            context_hash=p["context_hash"],model_revision=p["model_revision"],
            mode=p["mode"],ood=p["ood"]
        )
        refs=[]
        for kind,payload,secret,metadata in (artifacts or []):
            refs.append(self.vault.put(kind,payload,secret=secret,metadata=metadata).id)
        if external_artifact_ref:
            refs.append(external_artifact_ref)
        action=task.options.get(digit,DEFAULT_ACTIONS.get(digit))
        decision=HumanDecision(
            digit=digit,semantic_action=action,text=text,
            artifact_refs=tuple(refs),decided_at=datetime.now(timezone.utc).isoformat()
        )
        metrics=self.model.update(ctx,digit,prediction=pred)
        complete = (task.expected_artifact_type is None) or bool(refs)
        event=_event("HUMAN_DECISION" if complete else "HUMAN_DECISION_PARTIAL",task_id,{
            "digit":digit,
            "semantic_action":action,
            "text":text,
            "artifact_refs":[self.vault.model_projection(r) for r in refs],
            "prediction_ref":task.prediction_ref,
            "prediction_was_correct":pred.predicted_digit==digit,
            "model_metrics_after":metrics,
        })
        self.events.append(event)
        if complete:
            self.queue.resolve(task_id,event.id)
        else:
            task.state="WAITING_ARTIFACT"
        return decision,event

    def complete_with_external_artifact(self,task_id:str,artifact_ref:str):
        task=self.queue.get(task_id)
        if task.state not in {"OPEN","WAITING_ARTIFACT"}:
            raise ValueError("task not awaiting human artifact")
        if task.expected_artifact_type is None:
            raise ValueError("task does not require artifact completion")
        event=_event("HUMAN_ARTIFACT_CONFIRMED",task_id,{
            "artifact_ref":artifact_ref,
            "expected_artifact_type":task.expected_artifact_type,
        })
        self.events.append(event)
        self.queue.resolve(task_id,event.id)
        return event
