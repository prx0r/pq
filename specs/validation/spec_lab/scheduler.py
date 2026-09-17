from __future__ import annotations
from .models import ATask
from .policies import KernelPolicy, FINAL_POLICY
from .underengineer import task_priority

WAITING = {"WAITING_H", "WAITING_M", "FAILED", "DONE"}

def ready_tasks(tasks: list[ATask], *, policy: KernelPolicy = FINAL_POLICY) -> list[ATask]:
    by_id={t.id:t for t in tasks}

    # Historical failure mode: one human/money block stalls the mission.
    if not policy.branch_non_interference:
        if any(t.state in {"WAITING_H","WAITING_M"} for t in tasks):
            return []

    ready=[]
    for t in tasks:
        if t.state != "READY":
            continue
        blocked=False
        for dep in t.blocked_by:
            parent=by_id.get(dep)
            if not parent or parent.state != "DONE":
                blocked=True
                break
        if not blocked:
            ready.append(t)
    return sorted(ready,key=task_priority,reverse=True)

def apply_block(tasks: list[ATask], parent_atask: str, outcome: str) -> None:
    target=next(t for t in tasks if t.id==parent_atask)
    if outcome=="H_TASK":
        target.state="WAITING_H"
    elif outcome=="M_TASK":
        target.state="WAITING_M"
    elif outcome=="FAIL":
        target.state="FAILED"
    else:
        target.state="READY"

def resume(tasks: list[ATask], parent_atask: str) -> None:
    target=next(t for t in tasks if t.id==parent_atask)
    if target.state in {"WAITING_H","WAITING_M"}:
        target.state="READY"
