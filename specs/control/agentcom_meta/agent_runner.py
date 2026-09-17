from __future__ import annotations
import hashlib,json,os,shutil,subprocess,time
from dataclasses import dataclass,asdict
from pathlib import Path
from .canonical import obj_id
from .experiment import LaneSpec,DEFAULT_LANES

@dataclass(frozen=True)
class AgentRunRecord:
    lane_id:str
    policy:str
    contract_root:str
    proof_root:str
    returncode:int
    elapsed_s:float
    changed_files:tuple[str,...]
    artifact_hashes:tuple[tuple[str,str],...]
    stdout_path:str
    stderr_path:str
    record_id:str


def _hash_file(p:Path):
    h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()

def _snapshot(root:Path):
    out={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and '.git' not in p.parts and 'agent_run' not in p.parts:
            out[str(p.relative_to(root))]=_hash_file(p)
    return out

class FiveAgentProcessRunner:
    """Provider-neutral isolated-workspace harness for five coding agents.

    The agent process receives AGENTCOM_TASK_JSON and the same frozen roots. Its stdout
    is never treated as a proof verdict; this harness only records execution/artifacts.
    """
    def __init__(self,command:list[str],*,timeout_s=300,base_env:dict[str,str]|None=None):
        self.command=command;self.timeout_s=timeout_s;self.base_env=base_env or {}
    def run(self,base_workspace:str|Path,outdir:str|Path,contract_root:str,proof_root:str,*,spec_text:str,lanes=DEFAULT_LANES):
        if len(lanes)!=5:raise ValueError('five-agent-runner-requires-five')
        base=Path(base_workspace);out=Path(outdir);out.mkdir(parents=True,exist_ok=True);records=[]
        for lane in lanes:
            w=out/lane.id.replace(':','_');
            if w.exists():shutil.rmtree(w)
            shutil.copytree(base,w)
            before=_snapshot(w)
            task={"contract_root":contract_root,"proof_root":proof_root,"lane_id":lane.id,"policy":lane.policy,"mutation":lane.mutation,"exploration":lane.exploration,"spec":spec_text}
            task_path=w/'agent_task.json';task_path.write_text(json.dumps(task,indent=2))
            env={"PATH":os.environ.get('PATH',''),**self.base_env,"AGENTCOM_TASK_JSON":str(task_path),"AGENTCOM_POLICY":lane.policy,"AGENTCOM_LANE_ID":lane.id}
            t=time.monotonic()
            try:r=subprocess.run(self.command,cwd=w,env=env,capture_output=True,text=True,timeout=self.timeout_s)
            except subprocess.TimeoutExpired as e:
                rc=124;stdout=(e.stdout or '') if isinstance(e.stdout,str) else '';stderr=(e.stderr or '') if isinstance(e.stderr,str) else 'TIMEOUT'
            else:rc=r.returncode;stdout=r.stdout;stderr=r.stderr
            elapsed=time.monotonic()-t
            logs=w/'agent_run';logs.mkdir(exist_ok=True);sp=logs/'stdout.log';ep=logs/'stderr.log';sp.write_text(stdout);ep.write_text(stderr)
            after=_snapshot(w);changed=tuple(sorted(k for k,v in after.items() if before.get(k)!=v and k!='agent_task.json'))
            hashes=tuple((k,after[k]) for k in changed)
            rid=obj_id('agent-run',{"lane":lane.id,"contract_root":contract_root,"proof_root":proof_root,"returncode":rc,"hashes":hashes})
            rec=AgentRunRecord(lane.id,lane.policy,contract_root,proof_root,rc,round(elapsed,4),changed,hashes,str(sp),str(ep),rid);records.append(rec)
            (logs/'record.json').write_text(json.dumps(asdict(rec),indent=2))
        return tuple(records)
