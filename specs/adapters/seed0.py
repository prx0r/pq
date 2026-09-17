"""Seed0 adapter (devplan §4/§17): the experimental optimizer, referenced.

Uses real `~/seed0` primitives: learn.propose (shared failures → candidate
lessons, stops at proposed — never auto-applies) and tournament scoring
(via CLI on demand). Execution-policy families are named here so lanes can
reference them: policy.direct, policy.seeker3, policy.gitgoblin_first,
policy.test_first, policy.redteam_first, policy.repair_first,
policy.replace_component.
"""
import importlib.util
import os
import subprocess

from adapters import _env

SEED0_DEFAULT = "/home/ubuntu/seed0"
POLICIES = ("policy.direct", "policy.seeker3", "policy.gitgoblin_first",
            "policy.test_first", "policy.redteam_first", "policy.repair_first",
            "policy.replace_component")


def root():
    return _env.require_dir(
        _env.repo_root("AGENTCOM_SEED0_ROOT", SEED0_DEFAULT), "seed0")


def version():
    try:
        r = root()
        rev = subprocess.run(["git", "-C", r, "rev-parse", "HEAD"],
                             capture_output=True, text=True,
                             timeout=10).stdout.strip()
        available = True
    except Exception:  # noqa: BLE001
        r, rev, available = _env.repo_root("AGENTCOM_SEED0_ROOT",
                                           SEED0_DEFAULT), "unknown", False
    return {"repo": r, "rev": rev, "available": available,
            "policies": list(POLICIES)}


def _mod(name):
    path = os.path.join(root(), name + ".py")
    _env.require_file(path, "seed0")
    spec = importlib.util.spec_from_file_location("seed0_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def candidate_lessons(fails, min_seeds=2):
    """Real learn.propose: failures → clusters + proposals (status proposed).
    Nothing is applied here — promotion is a governed transition (ab5+)."""
    return _mod("learn").propose(fails, min_seeds=min_seeds)


def tournament_cmd(seed_dirs, model=""):
    """Reference to a real tournament run (executed by the operator, not
    imported — tournaments run untrusted seed code with timeouts). Returns
    the argv; AgentCom files the resulting tournament_*.jsonl as evidence."""
    cmd = ["python3", os.path.join(root(), "tournament.py")] + list(seed_dirs)
    if model:
        cmd += ["--model", model]
    return cmd
