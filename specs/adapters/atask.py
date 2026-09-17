"""A-Task adapter (devplan §25): execution authority stays in A-Task.

Operates a SANDBOX `.atask` dir (never the live `~/atask` checkout) via the
real `atask.py` CLI subprocess: init → add (evidence required) → run
start/usage/finish. DONE comes from A-Task's stoplight, read back here as
a reference. No local clone of task semantics.
"""
import json
import os
import subprocess

from adapters import _env

ATASK_DEFAULT_ROOT = "/home/ubuntu/atask"


def root():
    return _env.require_dir(
        _env.repo_root("AGENTCOM_ATASK_ROOT", ATASK_DEFAULT_ROOT), "atask")


def cli():
    return _env.require_file(os.path.join(root(), "atask.py"), "atask")


def version():
    try:
        cli()
        rev = subprocess.run(["git", "-C", root(),
                              "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
        available = True
    except Exception:  # noqa: BLE001
        rev, available = "unknown", False
    return {"cli": os.path.join(_env.repo_root(
        "AGENTCOM_ATASK_ROOT", ATASK_DEFAULT_ROOT), "atask.py"),
            "rev": rev, "available": available}


def _run(sandbox, *args):
    p = subprocess.run(["python3", cli(), "--dir",
                        os.path.join(sandbox, ".atask")] + list(args),
                       capture_output=True, text=True, timeout=60,
                       cwd=root())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def init_sandbox(sandbox):
    os.makedirs(sandbox, exist_ok=True)
    return _run(sandbox, "init")


def add_task(sandbox, task_id, summary, acceptance, evidence):
    args = ["add", "--id", task_id, "--summary", summary]
    for a in acceptance:
        args += ["--accept", a]
    for e in evidence:
        args += ["--evidence", e]
    return _run(sandbox, *args)


def run_cycle(sandbox, task_id, worker="agentcom", model="sim",
              input_tokens=0, output_tokens=0, cost=0.0):
    """start → usage → finish. Returns dict of raw outputs + refs."""
    rc1, o1 = _run(sandbox, "run", "start", "--id", task_id,
                   "--worker", worker, "--model", model)
    run_id = None
    try:
        for line in o1.splitlines():
            line = line.strip()
            if line.startswith("{"):
                run_id = json.loads(line).get("run_id", run_id)
    except ValueError:
        pass
    out = {"start": (rc1, o1), "run_id": run_id}
    if run_id:
        out["usage"] = _run(sandbox, "run", "usage", "--run", run_id,
                            "--input-tokens", str(input_tokens),
                            "--output-tokens", str(output_tokens),
                            "--cost", str(cost))
        out["finish"] = _run(sandbox, "run", "finish", "--run", run_id,
                             "--result", "completed")
    return out


def goal_check(sandbox):
    return _run(sandbox, "goal", "check")
