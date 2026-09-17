from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
import json,subprocess,re
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class HarborTrial:
    dataset:str
    agent:str
    model:str
    env:str|None=None
    n_concurrent:int=1
    extra_args:tuple[str,...]=()

    def command(self)->list[str]:
        cmd=["harbor","run","--dataset",self.dataset,"--agent",self.agent,"--model",self.model,"--n-concurrent",str(self.n_concurrent)]
        if self.env:cmd += ["--env",self.env]
        cmd += list(self.extra_args);return cmd

@dataclass(frozen=True)
class HarborQPTask:
    name:str
    instruction:str
    contract_root:str
    proof_root:str
    proof_id:str
    verifier_source:str
    dockerfile:str="FROM python:3.12-slim\nWORKDIR /workspace\n"
    network_mode:str="no-network"
    agent_timeout_sec:float=1800.0
    verifier_timeout_sec:float=120.0
    cpus:int=1
    memory_mb:int=2048
    tags:tuple[str,...]=("agentcom","qp-proof")

class HarborTaskCompiler:
    """Compile a frozen QP proof obligation into a standard local Harbor task.

    The verifier embedded here is an *evaluation verifier*. Its reward is candidate evidence,
    never QP settlement. Production use should supply a verifier whose source/program hash is
    already frozen by the AgentCom proof plan rather than generating grading logic ad hoc.
    """
    @staticmethod
    def _slug(name:str)->str:
        s=re.sub(r"[^a-zA-Z0-9_.-]+","-",name).strip("-.")
        if not s:raise ValueError("harbor-task-name-empty")
        return s[:120]

    def export(self,spec:HarborQPTask,out_root:str|Path)->dict[str,Any]:
        if spec.network_mode not in {"public","no-network","allowlist"}:raise ValueError("bad-network-mode")
        if not spec.contract_root.startswith("contract:"):raise ValueError("contract-root-required")
        if not spec.proof_root.startswith("proofroot:"):raise ValueError("proof-root-required")
        slug=self._slug(spec.name);root=Path(out_root)/slug
        if root.exists() and any(root.iterdir()):raise FileExistsError(root)
        (root/"environment").mkdir(parents=True,exist_ok=True);(root/"tests").mkdir(parents=True,exist_ok=True)
        tags=", ".join(json.dumps(x) for x in spec.tags)
        task_toml=f'''version = "1.0"\n\n[task]\nname = {json.dumps(slug)}\n\n[metadata]\ncategory = "agentcom-qp"\ntags = [{tags}]\ncontract_root = {json.dumps(spec.contract_root)}\nproof_root = {json.dumps(spec.proof_root)}\nproof_id = {json.dumps(spec.proof_id)}\n\n[agent]\ntimeout_sec = {float(spec.agent_timeout_sec)}\n\n[verifier]\ntimeout_sec = {float(spec.verifier_timeout_sec)}\nenvironment_mode = "separate"\n\n[environment]\ncpus = {int(spec.cpus)}\nmemory_mb = {int(spec.memory_mb)}\nnetwork_mode = {json.dumps(spec.network_mode)}\n\n[verifier.environment]\ncpus = {int(spec.cpus)}\nmemory_mb = {int(spec.memory_mb)}\nnetwork_mode = "no-network"\n'''
        (root/"task.toml").write_text(task_toml)
        (root/"instruction.md").write_text(spec.instruction.rstrip()+"\n")
        (root/"environment"/"Dockerfile").write_text(spec.dockerfile.rstrip()+"\n")
        verifier=spec.verifier_source.rstrip()+"\n"
        (root/"tests"/"verifier.py").write_text(verifier)
        test_sh='''#!/bin/sh\nset -eu\nmkdir -p /logs/verifier\nif python /tests/verifier.py; then\n  printf '{"qp_candidate":1,"verifier_exit":0}\\n' > /logs/verifier/reward.json\nelse\n  rc=$?\n  printf '{"qp_candidate":0,"verifier_exit":%s}\\n' "$rc" > /logs/verifier/reward.json\n  exit "$rc"\nfi\n'''
        p=root/"tests"/"test.sh";p.write_text(test_sh);p.chmod(0o755)
        (root/"tests"/"Dockerfile").write_text('FROM python:3.12-slim\nCOPY verifier.py /tests/verifier.py\nCOPY test.sh /tests/test.sh\nRUN chmod +x /tests/test.sh\n')
        meta={"schema":"agentcom.harbor-qp-task/0.1","contract_root":spec.contract_root,"proof_root":spec.proof_root,"proof_id":spec.proof_id,"verifier_sha256":sha256(verifier.encode()).hexdigest(),"instruction_sha256":sha256((spec.instruction.rstrip()+"\n").encode()).hexdigest(),"harbor_reward_is_qp_truth":False}
        (root/"qp_meta.json").write_text(json.dumps(meta,indent=2,sort_keys=True))
        return {"ok":True,"task_dir":str(root),"meta":meta,"command":["harbor","run","-p",str(root),"-a","<agent>","-m","<model>"]}

class HarborAdapter:
    """Harbor is an experiment/eval processor, never QP settlement."""
    def __init__(self,binary:str="harbor"):self.binary=binary
    def plan(self,trials:list[HarborTrial])->dict[str,Any]:
        return {"kind":"harbor-plan","trials":[{**asdict(t),"command":t.command()} for t in trials]}
    def run(self,trial:HarborTrial,*,timeout_s:int=3600)->dict[str,Any]:
        cmd=trial.command();cmd[0]=self.binary
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout_s)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr,"command":cmd}
    @staticmethod
    def summarize(rows:list[dict[str,Any]])->dict[str,Any]:
        # Correctness / QP-validity is lexicographically prior to Harbor reward.
        valid=[r for r in rows if r.get("qp_valid") is True]
        invalid=[r for r in rows if r.get("qp_valid") is not True]
        valid.sort(key=lambda r:(-float(r.get("reward",0)),float(r.get("cost",0)),r.get("id","")))
        return {"valid":valid,"excluded":invalid,"winner":valid[0] if valid else None}
