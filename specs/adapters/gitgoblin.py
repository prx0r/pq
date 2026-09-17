"""GitGoblin adapter: prebuild archaeology with honest limits.

Recon 2026-09-14: GitGoblin has NO capability-inventory search surface —
only entity substring search (MCP search_entities / REST /v1/search) over
repos/papers/devs/discussions. So this adapter does two things:
1. local archaeology NOW: keyword index over our own packages + checkouts
   (the reuse search we can actually run) → REUSE/BUILD verdicts;
2. remote entity search LATER: documents the exact MCP/REST call shape for
   live prebuild (needs a running GitGoblin service, not faked here).

Every BUILD task without a ReusePlan (or recorded exemption) is suspect —
enforced by the prebuild gate in core tests, not by this module.
"""
import os
import re
import subprocess

from adapters import _env

GG_DEFAULT = "/home/ubuntu/gitgoblin"
LOCAL_ROOTS = ("/agentcomfinal/packages", "/agentcomfinal/autobuild",
               "/agentcomfinal/core", "/agentcomfinal/adapters",
               "/home/ubuntu/gg-as/gitgoblin")


def root():
    return _env.require_dir(
        _env.repo_root("AGENTCOM_GITGOBLIN_ROOT", GG_DEFAULT), "gitgoblin")


def version():
    try:
        r = root()
        rev = subprocess.run(["git", "-C", r, "rev-parse", "HEAD"],
                             capture_output=True, text=True,
                             timeout=10).stdout.strip()
        available = True
    except Exception:  # noqa: BLE001
        r, rev, available = _env.repo_root("AGENTCOM_GITGOBLIN_ROOT",
                                           GG_DEFAULT), "unknown", False
    return {"repo": r, "rev": rev, "available": available,
            "remote_search": "MCP search_entities(query, entity_type, "
                             "sector, limit) / REST GET /v1/search "
                             "(needs live service)"}


def search_local(query, roots=None):
    """Keyword archaeology over local trees. Returns candidates:
    [{path, hits, verdict}] verdict REUSE if a README/schema/test cluster
    matches, else BUILD."""
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", query or "")]
    cands = []
    for root in (roots or LOCAL_ROOTS):
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            names = " ".join(files).lower()
            score = sum(1 for t in terms if t in names or t in dirpath.lower())
            if score <= 0:
                continue
            has = {f.lower() for f in files}
            reuse = bool({"readme.md", "readme"} & has) and (
                any(f.endswith(".py") for f in files)
                or any("schema" in f for f in files))
            cands.append({"path": dirpath, "hits": score,
                          "verdict": "REUSE" if reuse else "BUILD"})
    cands.sort(key=lambda c: (-c["hits"], c["path"]))
    return cands[:20]


def reuse_plan(requirement, query, exemption="", roots=None):
    """Prebuild record: same ContractRoot in, new PlanRoot out (verified by
    core.lineage.contract_invariant, not here)."""
    cands = search_local(query, roots)
    return {"requirement": requirement, "query": query,
            "candidates": cands, "exemption": exemption,
            "verdict": "EXEMPT" if exemption else (
                "REUSE" if any(c["verdict"] == "REUSE" for c in cands)
                else "BUILD")}
