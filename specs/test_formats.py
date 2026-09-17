"""Format bridges: ATIF export, memory projection, OTel mapping."""
import os
import sys

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
sys.path.insert(0, ROOT)

from trajectory import atif, memory, otel  # noqa: E402


def attempts():
    return [
        {"attempt_id": "ATT-0", "action": {"kind": "TEST", "description": "send probe"},
         "observed_effect": {"verdict": "FAIL", "reasons": ["no readback"]},
         "cost": {"duration_ms": 120, "tokens": None, "usd": 0.01}},
        {"attempt_id": "ATT-1", "action": {"kind": "TEST", "description": "send with readback"},
         "observed_effect": {"verdict": "PASS", "reasons": []},
         "cost": {"duration_ms": 340, "tokens": None, "usd": 0.02}},
    ]


def test_atif_export_shape():
    out = atif.from_trajectory({"trajectory_id": "t1", "model": "sim",
                                "attempts": attempts()},
                               agent={"name": "w", "version": "0.1.0"},
                               session_id="sess-1")
    ok, reasons = atif.check_shape(out)
    assert ok, reasons
    assert out["steps"][0]["observation"]["results"][0]["content"] == "FAIL"
    assert out["final_metrics"]["total_steps"] == 2
    assert out["final_metrics"]["total_cost_usd"] == 0.03


def test_atif_shape_rejects_garbage():
    ok, reasons = atif.check_shape({"nope": True})
    assert not ok and reasons


def test_memory_projection_and_fidelity():
    proj = memory.project(attempts(), source="test")
    assert proj["records"][0]["role"] == "meta"
    assert proj["reduction"] >= 1.0  # measured, not claimed
    ok, missing = memory.fidelity(attempts(), proj)
    assert ok, missing


def test_memory_quality_axes():
    cand = {"idea": "cache readback receipts, for example keyed by order id",
            "statement": "receipts speed up retry verdicts"}
    held = {"task_text": "prove send with readback receipts",
            "needs": ["readback", "receipts"]}
    axes = memory.quality_axes(cand, held)
    assert axes["adherence"] is True and axes["retrieval"] is True
    assert axes["hygiene"] is True
    assert set(axes) == {"adherence", "retrieval", "generalization", "hygiene"}


def test_otel_span_shape():
    spans = otel.to_spans([{"attempt_id": "ATT-0", "model": "m",
                            "run_id": "r1",
                            "observed_effect": {"verdict": "PASS"},
                            "cost": {"tokens": 10}}])
    (s,) = spans
    assert s["kind"] == "CLIENT" and s["status"] == {"code": "OK"}
    assert s["attributes"]["gen_ai.request.model"] == "m"
    assert s["attributes"]["gen_ai.usage.input_tokens"] == 10
    assert otel.to_spans([{"attempt_id": "X"}])[0]["status"] == {"code": "UNSET"}


def test_bank_files_all_views(tmp_path):
    from trajectory import bank, trajectory as _t
    t = _t.build("cr", "pr", "policy.seeker3",
                 [{"attempt_id": "ATT-0",
                   "action": {"description": "probe"},
                   "observed_effect": {"verdict": "PASS", "reasons": []},
                   "cost": {}}],
                 {"x": "U"}, {"x": "T"},
                 cost={"tokens": 1, "wall_ms": 2, "usd": 0.01,
                       "human_minutes": 0})
    out = bank.file_trajectory(str(tmp_path), t, agent={"name": "w"},
                               session_id="s")
    assert len(out["files"]) == 3
    assert all(os.path.exists(p) for p in out["files"])
    idx = open(os.path.join(str(tmp_path), "index.jsonl")).read()
    assert "reduction" in idx


def test_bank_routes_l0_to_observations(tmp_path):
    from trajectory import bank, trajectory as _t
    t = _t.build("cr", "pr", "p", [], {"x": "U"}, {"x": "U"},
                 cost={"tokens": 0, "wall_ms": 0, "usd": 0,
                       "human_minutes": 0})
    assert t["level"] == "L0-observation"
    out = bank.file_trajectory(str(tmp_path), t)
    assert out["tier"] == "observations"
    assert "/observations/" in out["dir"]


def test_bank_refuses_l0_under_verified(tmp_path):
    from trajectory import bank, trajectory as _t
    t = _t.build("cr", "pr", "p", [], {"x": "U"}, {"x": "U"},
                 cost={"tokens": 0, "wall_ms": 0, "usd": 0,
                       "human_minutes": 0})
    with pytest.raises(bank.TierRefused):
        bank.file_at(str(tmp_path), t, "verified")
    with pytest.raises(bank.TierRefused):
        bank.file_at(str(tmp_path), t, "promoted")


def test_bank_l1_files_verified_l5_needs_receipt(tmp_path):
    from trajectory import bank, trajectory as _t
    t = _t.build("cr", "pr", "p", [], {"x": "U"}, {"x": "T"},
                 cost={"tokens": 0, "wall_ms": 0, "usd": 0,
                       "human_minutes": 0})
    t["level"] = "L1-fact"
    out = bank.file_trajectory(str(tmp_path), t)
    assert out["tier"] == "verified"
    t["level"] = "L5-promoted"
    with pytest.raises(bank.TierRefused):
        bank.file_trajectory(str(tmp_path), t)
    t["promotion_receipt"] = "pr:1"
    out = bank.file_trajectory(str(tmp_path), t)
    assert out["tier"] == "promoted"


def test_bank_refuses_on_fidelity_loss(monkeypatch):
    import trajectory.bank as _b
    import trajectory.memory as _m
    atts = [{"attempt_id": "ATT-9",
             "observed_effect": {"verdict": "PASS"},
             "action": {}, "cost": {}}]
    ok, missing = _m.fidelity(
        atts, {"records": [{"role": "observation", "content": "unrelated"}]})
    assert not ok and missing
    monkeypatch.setattr(_m, "project",
                        lambda *a, **k: {"records": [], "reduction": 0})
    with pytest.raises(_b.FidelityRefused):
        _b.file_trajectory("/tmp/never-written-zz",
                           {"trajectory_id": "t", "attempts": atts,
                            "policy_id": "p", "level": "L0-observation"})
