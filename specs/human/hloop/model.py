from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import hashlib, math, json

# Digits are intentionally tiny motor primitives. Their semantics are configurable
# per queue/task, but the default macro map is stable enough for muscle memory.
DEFAULT_ACTIONS = {
    0: "ABSTAIN_OR_NEED_CONTEXT",
    1: "REJECT",
    2: "DEFER",
    3: "REPLAN",
    4: "CHEAPER_ROUTE",
    5: "CONTINUE",
    6: "APPROVE_ONCE",
    7: "APPROVE_BOUNDED",
    8: "PROMOTE_PREFERRED_ROUTE",
    9: "MAX_AUTONOMY_WITHIN_GRANT",
}

def action_label(digit: int, mapping: dict[int,str] | None=None) -> str:
    m=mapping or DEFAULT_ACTIONS
    if digit not in m:
        raise ValueError("digit must be 0..9")
    return m[digit]

@dataclass(frozen=True)
class HumanContext:
    task_kind: str
    proof_family: str
    consequence_class: str
    risk_band: str
    project: str = ""
    processor_id: str = ""
    model_id: str = ""
    route_id: str = ""
    tags: tuple[str,...] = ()
    budget_pressure: str = "GREEN"
    machine_recommendation: int | None = None

@dataclass(frozen=True)
class HumanPrediction:
    predicted_digit: int
    probabilities: tuple[float,...]
    confidence: float
    entropy: float
    context_hash: str
    model_revision: int
    mode: str  # HUMAN | SHADOW | SUGGEST | AUTO_ELIGIBLE
    ood: bool

@dataclass(frozen=True)
class HumanDecision:
    digit: int
    semantic_action: str
    text: str | None = None
    artifact_refs: tuple[str,...] = ()
    decided_at: str | None = None

def _stable_token(s: str) -> int:
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],"big")

def _softmax(xs):
    m=max(xs)
    ex=[math.exp(x-m) for x in xs]
    z=sum(ex)
    return [x/z for x in ex]

class HLoopPolicyModel:
    """Tiny online 10-way policy predictor.

    It predicts *the operator's action*, never objective truth. The model is
    deliberately simple, inspectable and dependency-free: feature hashing +
    multiclass softmax SGD. Production can swap the learner while keeping the
    event protocol and calibration gates stable.
    """
    def __init__(
        self,
        *,
        dim: int = 256,
        lr: float = 0.08,
        l2: float = 1e-5,
        auto_min_examples: int = 50,
        auto_confidence: float = 0.92,
        shadow_min_examples: int = 12,
        ood_min_seen: int = 3,
    ):
        self.dim=dim; self.lr=lr; self.l2=l2
        self.auto_min_examples=auto_min_examples
        self.auto_confidence=auto_confidence
        self.shadow_min_examples=shadow_min_examples
        self.ood_min_seen=ood_min_seen
        self.weights=[[0.0]*dim for _ in range(10)]
        self.n=0
        self.revision=0
        self.context_counts={}
        self.correct=0
        self.logloss_sum=0.0
        self.brier_sum=0.0

    def _features(self, ctx: HumanContext):
        raw={
            "task_kind":ctx.task_kind,
            "proof_family":ctx.proof_family,
            "consequence_class":ctx.consequence_class,
            "risk_band":ctx.risk_band,
            "project":ctx.project,
            "processor_id":ctx.processor_id,
            "model_id":ctx.model_id,
            "route_id":ctx.route_id,
            "budget_pressure":ctx.budget_pressure,
            "machine_recommendation":str(ctx.machine_recommendation),
        }
        toks=["bias=1"]
        toks += [f"{k}={v}" for k,v in raw.items() if v not in ("",None)]
        toks += [f"tag={x}" for x in ctx.tags]
        # Selected conjunctions improve small-data learning.
        toks += [
            f"kind:risk={ctx.task_kind}:{ctx.risk_band}",
            f"proof:consequence={ctx.proof_family}:{ctx.consequence_class}",
        ]
        feats={}
        for tok in toks:
            h=_stable_token(tok)
            idx=h % self.dim
            sign=1.0 if ((h >> 8) & 1)==0 else -1.0
            feats[idx]=feats.get(idx,0.0)+sign
        return feats

    def _bucket(self,ctx: HumanContext):
        key=(ctx.task_kind,ctx.proof_family,ctx.consequence_class,ctx.risk_band)
        return "|".join(key)

    def predict(self, ctx: HumanContext) -> HumanPrediction:
        f=self._features(ctx)
        logits=[sum(w[i]*v for i,v in f.items()) for w in self.weights]
        p=_softmax(logits)
        digit=max(range(10),key=lambda i:p[i])
        conf=p[digit]
        ent=-sum(x*math.log(max(x,1e-12)) for x in p)
        bucket=self._bucket(ctx)
        seen=self.context_counts.get(bucket,0)
        ood=seen < self.ood_min_seen

        if self.n < self.shadow_min_examples:
            mode="HUMAN"
        elif ood:
            mode="SHADOW"
        elif self.n < self.auto_min_examples or conf < self.auto_confidence:
            mode="SUGGEST"
        else:
            mode="AUTO_ELIGIBLE"

        ch=hashlib.sha256(json.dumps(asdict(ctx),sort_keys=True,default=list).encode()).hexdigest()
        return HumanPrediction(
            predicted_digit=digit,
            probabilities=tuple(p),
            confidence=conf,
            entropy=ent,
            context_hash="sha256:"+ch,
            model_revision=self.revision,
            mode=mode,
            ood=ood,
        )

    def update(self, ctx: HumanContext, actual_digit: int, prediction: HumanPrediction | None=None):
        if actual_digit not in range(10):
            raise ValueError("actual_digit must be 0..9")
        pred=prediction or self.predict(ctx)
        # Critical invariant: caller should normally pass the prediction made
        # before the human answer, so evaluation is not post-hoc.
        f=self._features(ctx)
        p=list(pred.probabilities)
        for k in range(10):
            y=1.0 if k==actual_digit else 0.0
            grad=p[k]-y
            wk=self.weights[k]
            for i,v in f.items():
                wk[i] -= self.lr*(grad*v + self.l2*wk[i])
        self.n += 1
        self.revision += 1
        bucket=self._bucket(ctx)
        self.context_counts[bucket]=self.context_counts.get(bucket,0)+1
        self.correct += int(pred.predicted_digit==actual_digit)
        self.logloss_sum += -math.log(max(p[actual_digit],1e-12))
        self.brier_sum += sum((p[k]-(1 if k==actual_digit else 0))**2 for k in range(10))/10
        return self.metrics()

    def metrics(self):
        return {
            "n":self.n,
            "revision":self.revision,
            "accuracy":self.correct/self.n if self.n else None,
            "logloss":self.logloss_sum/self.n if self.n else None,
            "brier":self.brier_sum/self.n if self.n else None,
            "context_buckets":len(self.context_counts),
        }
