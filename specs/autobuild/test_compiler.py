"""Compiler + E4 tournament proof suite."""
import copy
import os
import sys

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agentcombuild", "autobuild3", "src"))
sys.path.insert(0, os.path.join(ROOT, "agentcombuild", "agentloop", "src"))

from autobuild.compiler import actuality_compile as AC  # noqa: E402
from experiments.policies import tournament_e4 as E4  # noqa: E402


def test_uk_compiles_clean():
    c = AC.compile_uk()
    assert len(c["leaves"]) == 7
    ok, reasons = AC.check_compilable(c)
    assert ok, reasons
    assert not c["unprovable"]


def test_unprovable_leaf_flagged():
    bad = copy.deepcopy(AC.UK_LEAVES)
    del bad[3]["judge"]
    c = AC.compile_contract(AC.UK_CLAIM, bad)
    assert c["unprovable"] == ["response-constructed"]
    ok, _ = AC.check_compilable(c)
    assert not ok


def test_contract_stable_plan_moves():
    a = AC.compile_uk(plan_ref="route-A")
    b = AC.compile_uk(plan_ref="route-B")
    assert a["contract_root"] == b["contract_root"]  # WHAT frozen
    assert a["plan_root"] != b["plan_root"]  # HOW moved
    assert len(a["contract_root"]) > 20  # full SHA-256, never truncated


def test_no_agent_judges_quality():
    c = AC.compile_uk()
    for leaf in c["leaves"]:
        assert leaf["judge"]["engine"] in ("schema", "cel", "rego", "wasm")


def test_e4_winner_cheapest_passing_lane():
    out = E4.run()
    assert out["mode"] == "SIMULATED"
    assert out["tournament"]["winner"] == "gitgoblin-first"
    assert [n for n, _ in out["tournament"]["ranking"]][0] == "gitgoblin-first"


def test_e4_rogue_disqualified():
    out = E4.run()
    assert out["disqualified"] == [{"lane": "rogue",
                                    "reason": "contract-mismatch"}]
    assert "rogue" not in [n for n, _ in out["tournament"]["ranking"]]


def test_e4_corpus_and_lessons_banked(tmp_path):
    p = str(tmp_path / "e4.json")
    out = E4.run(p)
    assert set(out["trajectories"]) == {"direct", "seeker3", "gitgoblin-first"}
    assert os.path.exists(p)
    assert "proposals" in out["lessons"]  # real seed0.learn.propose ran
    assert any(t["level"] == "L0-observation"
               for t in out["trajectories"].values())


def test_contract_root_changes_on_proof_semantics():
    """Constitutional (test.md P0): WHAT changes move ContractRoot."""
    import copy
    base = AC.compile_uk()
    mutations = {
        "judge": {"engine": "cel", "expression": "e.status == 200"},
        "evidence_schema": {"type": "object", "required": ["other"]},
        "evidence_class": "direct",
        "freshness_s": 30 * 86400,
        "authority": "none",
        "proof_requirement": 0,
    }
    changed = dict(mutations)
    changed["evidence_class"] = "external_readback"  # outbound-sent is direct
    idx = 4  # outbound-sent leaf
    for field, value in changed.items():
        mut = copy.deepcopy(AC.UK_LEAVES)
        mut[idx][field] = value
        c = AC.compile_contract(AC.UK_CLAIM, mut)
        assert c["contract_root"] != base["contract_root"], field


def test_contract_stable_plan_moves_on_how():
    """HOW changes (probe/repo/model/policy/runner) keep ContractRoot."""
    import copy
    base = AC.compile_uk(plan_ref="route-A")
    for route in ({"probe": "other.send"}, {"repo": "other/repo"},
                  {"model": "other-model"}, {"policy": "other-policy"},
                  {"runner": "other-runner"}):
        mut = copy.deepcopy(AC.UK_LEAVES)
        mut[4]["probe"] = route.get("probe", mut[4]["probe"])
        c = AC.compile_contract(AC.UK_CLAIM, mut, plan_ref="route-A",
                                route=route)
        assert c["contract_root"] == base["contract_root"], route
        assert c["plan_root"] != base["plan_root"], route
