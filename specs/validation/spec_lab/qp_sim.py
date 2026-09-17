from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from .canonical import digest, full_id
from .models import ActualityContract, Claim, Evidence, ProofReceipt
from .policies import KernelPolicy, FINAL_POLICY

class QPError(RuntimeError):
    pass


@dataclass
class ProbeSpec:
    id: str
    source_class: str
    channel: str
    trusted: bool = True
    can_independently_readback: bool = False

@dataclass
class ProbeRegistry:
    probes: dict[str, ProbeSpec] = field(default_factory=dict)

    def register(self, spec: ProbeSpec) -> None:
        if spec.id in self.probes:
            raise QPError(f"duplicate probe {spec.id}")
        self.probes[spec.id] = spec

    def spec(self, probe_id: str) -> ProbeSpec | None:
        return self.probes.get(probe_id)

    def is_independent_readback(self, probe_id: str) -> bool:
        spec=self.probes.get(probe_id)
        return bool(spec and spec.trusted and spec.can_independently_readback)


def make_evidence(
    claim_id: str,
    *,
    probe_id: str,
    value: Any,
    observed_at: str,
    source_class: str = "probe",
    independent: bool = False,
    environment_root: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Evidence:
    body={
        "claim_id":claim_id,
        "probe_id":probe_id,
        "value":value,
        "observed_at":observed_at,
        "source_class":source_class,
        "independent":independent,
        "environment_root":environment_root,
        "metadata":metadata or {},
    }
    artifact_hash=digest("evidence-artifact",body)
    return Evidence(
        id=full_id("evidence",body),
        claim_id=claim_id,
        probe_id=probe_id,
        observed_at=observed_at,
        value=value,
        source_class=source_class,
        artifact_hash=artifact_hash,
        independent=independent,
        environment_root=environment_root,
        metadata=metadata or {},
    )

def _age_seconds(observed_at: str, now: str) -> float:
    a=datetime.fromisoformat(observed_at.replace("Z","+00:00"))
    b=datetime.fromisoformat(now.replace("Z","+00:00"))
    return (b-a).total_seconds()

def settle_claim(
    contract: ActualityContract,
    claim_id: str,
    evidence: list[Evidence],
    *,
    now: str,
    judge: Callable[[Claim, list[Evidence]], str] | None = None,
    evaluator_root: str | None = None,
    state_before: str = "sha256:state-before",
    policy: KernelPolicy = FINAL_POLICY,
    probe_registry: ProbeRegistry | None = None,
) -> ProofReceipt:
    claim=next((c for c in contract.claims if c.id==claim_id),None)
    if not claim:
        raise QPError("unknown claim")
    if claim.kind!="leaf":
        raise QPError("reference simulator settles leaves only")

    if policy.freeze_contract and evaluator_root is not None:
        allowed=set(contract.evaluator_roots.values())
        if allowed and evaluator_root not in allowed:
            raise QPError("evaluator mutation")

    matching=[e for e in evidence if e.claim_id==claim_id]
    gates=[]

    if not matching:
        result="UNKNOWN"
        gates.append({"id":"evidence.present","result":"FAIL"})
    else:
        gates.append({"id":"evidence.present","result":"PASS"})
        result="TRUE"

    if matching and claim.freshness_seconds is not None:
        fresh=all(_age_seconds(e.observed_at,now)<=claim.freshness_seconds for e in matching)
        gates.append({"id":"evidence.fresh","result":"PASS" if fresh else "FAIL"})
        if not fresh:
            result="UNKNOWN"

    if policy.independent_readback and claim.independent_readback_required:
        # The Evidence object's `independent` field is descriptive only.
        # Independence is authority/trust metadata owned by the probe registry,
        # not something the worker/model may self-assert.
        independent=bool(probe_registry) and any(
            probe_registry.is_independent_readback(e.probe_id) for e in matching
        )
        gates.append({"id":"independent.readback","result":"PASS" if independent else "FAIL"})
        if not independent:
            result="UNKNOWN"

    if judge is not None and matching:
        judged=judge(claim,matching)
        if judged not in {"TRUE","FALSE","UNKNOWN"}:
            raise QPError("judge emitted invalid bool3")
        gates.append({"id":"claim.judge","result":"PASS" if judged=="TRUE" else judged})
        result=judged if result!="UNKNOWN" else "UNKNOWN"

    if policy.require_proofs and not claim.proof_id:
        raise QPError("claim lacks proof binding")

    state_after=digest("claim-state",{
        "state_before":state_before,
        "contract_root":contract.contract_root,
        "claim_id":claim_id,
        "result":result,
        "evidence_ids":[e.id for e in matching],
    })
    body={
        "contract_root":contract.contract_root,
        "claim_id":claim_id,
        "result":result,
        "evidence_ids":[e.id for e in matching],
        "gate_results":gates,
        "state_before":state_before,
        "state_after":state_after,
    }
    return ProofReceipt(
        id=full_id("qpproof",body),
        contract_root=contract.contract_root,
        claim_id=claim_id,
        result=result,
        evidence_ids=[e.id for e in matching],
        gate_results=gates,
        state_before=state_before,
        state_after=state_after,
        proof_level=9 if result=="TRUE" else 0,
    )

def roots_actuality(contract: ActualityContract, leaf_results: dict[str,str]) -> dict[str,str]:
    by={c.id:c for c in contract.claims}
    out=dict(leaf_results)
    pending=[c for c in contract.claims if c.kind=="root"]
    changed=True
    while changed:
        changed=False
        for c in pending:
            vals=[out.get(dep,"UNKNOWN") for dep in c.depends_on]
            if c.logic=="ALL":
                value="FALSE" if "FALSE" in vals else ("TRUE" if vals and all(v=="TRUE" for v in vals) else "UNKNOWN")
            else:
                value="TRUE" if "TRUE" in vals else ("FALSE" if vals and all(v=="FALSE" for v in vals) else "UNKNOWN")
            if out.get(c.id)!=value:
                out[c.id]=value;changed=True
    return out

def mandatory_actuality_true(contract: ActualityContract, leaf_results: dict[str,str]) -> bool:
    resolved=roots_actuality(contract,leaf_results)
    mandatory_roots=[c for c in contract.claims if c.kind=="root" and c.mandatory]
    return bool(mandatory_roots) and all(resolved.get(c.id)=="TRUE" for c in mandatory_roots)
