from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, hashlib

@dataclass(frozen=True)
class HarborTrialReceipt:
    id: str
    task_id: str
    processor_root: str
    contract_root: str
    obligation_id: str
    reward: dict[str,float]
    trajectory_ref: str | None
    environment_ref: str | None
    qp_valid: bool = False

def import_reward(path:Path)->dict[str,float]:
    if path.name.endswith(".json"):
        data=json.loads(path.read_text())
        out={}
        for k,v in data.items():
            if not isinstance(v,(int,float)):
                raise ValueError("Harbor reward metrics must be numeric")
            out[k]=float(v)
        return out
    return {"score":float(path.read_text().strip())}

def trial_receipt(
    *,task_id,processor_root,contract_root,obligation_id,reward,
    trajectory_ref=None,environment_ref=None,
):
    body={
        "task_id":task_id,"processor_root":processor_root,
        "contract_root":contract_root,"obligation_id":obligation_id,
        "reward":reward,"trajectory_ref":trajectory_ref,
        "environment_ref":environment_ref,
    }
    rid="harbor:"+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    return HarborTrialReceipt(id=rid,qp_valid=False,**body)
