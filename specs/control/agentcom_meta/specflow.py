from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any
import re
from .canonical import obj_id
from .planner import ProofNeed

NORMATIVE_RE=re.compile(r"\b(MUST|MUST NOT|SHALL|NEVER|AT MOST|REQUIRES?|FINAL ACCEPTANCE)\b",re.I)

@dataclass(frozen=True)
class Requirement:
    id:str
    claim:str
    source_line:int
    proof_class:str
    kind:str
    required_capabilities:tuple[str,...]
    consequential:bool=False
    external:bool=False
    human_boundary:str|None=None

@dataclass(frozen=True)
class CompiledSpec:
    source_sha:str
    requirements:tuple[Requirement,...]
    contract_root:str
    proof_root:str

    def proof_needs(self)->list[ProofNeed]:
        return [ProofNeed(r.id,r.required_capabilities,r.proof_class,r.external,r.consequential,1.0) for r in self.requirements]


def _classify(text:str)->tuple[str,str,tuple[str,...],bool,bool,str|None]:
    s=text.lower()
    # order matters: autonomy/learning are stronger than ordinary local behavior.
    if any(x in s for x in ("learn from every 0-9", "autonomy", "predict the human", "keypress")):
        return "Q8","autonomy",("human.policy.prediction","human.policy.calibration"),False,False,None
    if any(x in s for x in ("run 2", "run2", "reuse verified", "improve from run 1", "tournament")):
        return "Q7","learning",("experiment.ranking","candidate.lesson"),False,False,None
    if any(x in s for x in ("send", "dispatch", "publish", "purchase", "spend", "external action")):
        return "Q6","consequential",("action.ready","effect.attempted","readback.independent"),True,True,"AUTHORIZATION"
    if any(x in s for x in ("api key", "secret", "otp", "2fa", "credential")):
        return "Q5","secret",("human.decision",),False,False,"SECRET"
    if any(x in s for x in ("create account", "kyc", "identity")):
        return "Q5","identity",("human.decision",),False,False,"IDENTITY"
    if any(x in s for x in ("independent readback", "independent provider", "external readback", "provider-side")):
        return "Q5","readback",("probe.target","readback.independent"),False,True,None
    if any(x in s for x in ("persistent", "sqlite", "restart", "audit", "idempotent", "deduplicate", "dedup")):
        return "Q3","stateful-local",("work.minimal_plan","artifact.candidate"),False,False,None
    if any(x in s for x in ("mobile", "dashboard", "ui", "csv", "api", "endpoint", "health")):
        return "Q2","local-product",("work.minimal_plan","artifact.candidate"),False,False,None
    if any(x in s for x in ("preference", "choose default", "layout")):
        return "Q4","preference",("human.decision",),False,False,"PREFERENCE"
    return "Q2","local",("work.minimal_plan","artifact.candidate"),False,False,None


def compile_spec(text:str)->CompiledSpec:
    if not text.strip(): raise ValueError("empty-spec")
    lines=text.splitlines();reqs=[];seen=set()
    for i,line in enumerate(lines,1):
        raw=line.strip().lstrip("-* ").strip()
        if not raw or not NORMATIVE_RE.search(raw):continue
        # Canonical claims are verbatim normative spans; no model paraphrase becomes truth.
        if raw in seen:continue
        seen.add(raw)
        q,kind,caps,cons,ext,h=_classify(raw)
        rid=f"R{len(reqs)+1}"
        reqs.append(Requirement(rid,raw,i,q,kind,caps,cons,ext,h))
    if not reqs:raise ValueError("no-normative-requirements")
    source_sha=obj_id("spec-source",text)
    contract_payload={"source":source_sha,"requirements":[asdict(r) for r in reqs]}
    contract_root=obj_id("contract",contract_payload)
    proof_payload=[{"id":r.id,"claim":r.claim,"proof_class":r.proof_class,"capabilities":r.required_capabilities,"consequential":r.consequential,"external":r.external} for r in reqs]
    proof_root=obj_id("proofroot",{"contract_root":contract_root,"proofs":proof_payload})
    return CompiledSpec(source_sha,tuple(reqs),contract_root,proof_root)


def compile_file(path:str|Path)->CompiledSpec:
    return compile_spec(Path(path).read_text())
