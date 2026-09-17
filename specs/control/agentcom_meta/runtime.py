from __future__ import annotations
import json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable,Any
from .processor import ProcessorManifest,ProcessorContext,ProcessorResult,ProcessorStatus
from .canonical import sha256_hex

SOVEREIGN_KEYS={"proof_status","settled","qp_receipt","authority_grant","grant_signature"}

def _contains_sovereign(value:Any)->bool:
    if isinstance(value,dict):
        if SOVEREIGN_KEYS & set(value): return True
        return any(_contains_sovereign(v) for v in value.values())
    if isinstance(value,(list,tuple)):
        return any(_contains_sovereign(v) for v in value)
    return False

class ProcessorRuntime:
    def __init__(self,services:dict[str,Callable]|None=None):self.services=services or {}
    def _authority_ok(self,m:ProcessorManifest,ctx:ProcessorContext)->tuple[bool,str]:
        if not m.authority_required:return True,"not-required"
        if not ctx.authority_refs:return False,"authority-required"
        verifier=self.services.get("authority_verifier")
        if verifier is None:return False,"authority-verifier-unconfigured"
        try:
            ok=bool(verifier(m,ctx))
        except Exception:
            return False,"authority-verifier-error"
        return (True,"authorized") if ok else (False,"authority-invalid")
    def run_callable(self,m:ProcessorManifest,fn:Callable[[dict,ProcessorContext],dict],inputs:dict,ctx:ProcessorContext)->ProcessorResult:
        m.validate();start=datetime.now(timezone.utc).isoformat();h=sha256_hex(inputs)
        if m.seed_required and ctx.seed is None:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="seed-required")
        auth,reason=self._authority_ok(m,ctx)
        if not auth:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.BLOCKED,h,failure_code=reason)
        t=time.monotonic()
        try:
            out=fn(inputs,ctx)
        except Exception as e:
            return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.FAILED,h,failure_code="processor-exception",detail=repr(e),started_at=start,ended_at=datetime.now(timezone.utc).isoformat())
        elapsed=time.monotonic()-t
        if elapsed>m.timeout_s:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.TIMED_OUT,h,failure_code="timeout",detail=f"elapsed={elapsed:.3f}")
        if not isinstance(out,dict):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="invalid-output-schema")
        if _contains_sovereign(out):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="sovereign-output-forbidden")
        caps=tuple(sorted(set(out.get("capabilities_added",()))&set(m.provides)))
        evidence=out.get("evidence",[])
        if not isinstance(evidence,list):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="invalid-evidence-schema")
        return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.EXECUTED,h,outputs=out.get("outputs",{}),evidence=evidence,capabilities_added=caps,cost=out.get("cost",{}),detail=out.get("detail",""),started_at=start,ended_at=datetime.now(timezone.utc).isoformat(),replay_hash=sha256_hex({"inputs":inputs,"outputs":out}))

    def run_command(self,m:ProcessorManifest,command:list[str],inputs:dict,ctx:ProcessorContext,*,cwd:str|Path|None=None,env_allowlist:tuple[str,...]=("PATH",))->ProcessorResult:
        m.validate();h=sha256_hex(inputs);start=datetime.now(timezone.utc).isoformat()
        if m.seed_required and ctx.seed is None:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="seed-required")
        auth,reason=self._authority_ok(m,ctx)
        if not auth:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.BLOCKED,h,failure_code=reason)
        env={k:os.environ[k] for k in env_allowlist if k in os.environ};env["AGENTCOM_PROCESSOR_INPUT"]=json.dumps(inputs)
        try:r=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=m.timeout_s)
        except subprocess.TimeoutExpired:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.TIMED_OUT,h,failure_code="timeout")
        if r.returncode!=0:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.FAILED,h,failure_code="nonzero-exit",detail=(r.stderr or r.stdout)[-1000:])
        try:out=json.loads(r.stdout)
        except Exception:return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="invalid-json-output",detail=r.stdout[-1000:])
        if not isinstance(out,dict):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="invalid-output-schema")
        if _contains_sovereign(out):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="sovereign-output-forbidden")
        evidence=out.get("evidence",[])
        if not isinstance(evidence,list):return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.REJECTED,h,failure_code="invalid-evidence-schema")
        caps=tuple(sorted(set(out.get("capabilities_added",()))&set(m.provides)))
        return ProcessorResult(m.id,m.manifest_id,ProcessorStatus.EXECUTED,h,outputs=out.get("outputs",{}),evidence=evidence,capabilities_added=caps,cost=out.get("cost",{}),started_at=start,ended_at=datetime.now(timezone.utc).isoformat(),replay_hash=sha256_hex({"command":command,"inputs":inputs,"stdout":out}))
