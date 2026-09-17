"""H-task and harness deep tests — state machine edges, tool parsing, privacy.

Covers the H-task lifecycle edge cases and the harness's parse_tool regex.
"""
from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from agentcom.htasks.queue import HTask, HQueue
from harness import parse_tool


# ── H-task state machine edge cases ────────────────────────────────────

def test_invalid_kind_raises():
    with pytest.raises(ValueError, match="unknown kind"):
        HTask("t", "invalid", "q?")

def test_all_valid_kinds():
    for kind in ("digit", "confirm", "secret", "authority"):
        t = HTask("t", kind, "q?")
        assert t.kind == kind

def test_display_from_emitted():
    t = HTask("t", "digit", "Q?")
    v = t.display()
    assert t.state == "displayed"
    assert v["task_id"] == "t"
    assert v["state"] == "displayed"

def test_display_from_wrong_state():
    t = HTask("t", "digit", "Q?")
    t.display()
    with pytest.raises(ValueError, match="displayed"):
        t.display()  # already displayed

def test_acknowledge_from_displayed():
    t = HTask("t", "digit", "Q?")
    t.display()
    t.acknowledge()
    assert t.state == "acknowledged"

def test_acknowledge_from_emitted_fails():
    t = HTask("t", "digit", "Q?")
    with pytest.raises(ValueError, match="emitted"):
        t.acknowledge()

def test_answer_from_displayed():
    t = HTask("t", "digit", "Q?")
    t.display()
    a = t.answer_task("42")
    assert t.state == "answered"
    assert a["value"] == "42"

def test_answer_from_acknowledged():
    t = HTask("t", "confirm", "Go?")
    t.display()
    t.acknowledge()
    a = t.answer_task("yes")
    assert t.state == "answered"
    assert a["value"] == "yes"

def test_answer_from_emitted_fails():
    t = HTask("t", "digit", "Q?")
    with pytest.raises(ValueError, match="emitted"):
        t.answer_task("42")

def test_secret_kind_cannot_answer():
    t = HTask("t", "secret", "paste key")
    t.display()
    t.acknowledge()
    with pytest.raises(ValueError, match="secrets deposit"):
        t.answer_task("my-secret")

def test_expire_from_emitted():
    t = HTask("t", "digit", "Q?", lease_s=1)
    t.expire(t.deadline)
    assert t.state == "expired"
    assert t.answer["value"] == "deny"
    assert t.answer["expired"] is True

def test_expire_from_displayed():
    t = HTask("t", "digit", "Q?", lease_s=1)
    t.display()
    t.expire(t.deadline)
    assert t.state == "expired"
    assert t.answer["value"] == "deny"

def test_expire_from_acknowledged():
    t = HTask("t", "confirm", "Go?", lease_s=1)
    t.display()
    t.acknowledge()
    t.expire(t.deadline)
    assert t.state == "expired"
    assert t.answer["value"] == "deny"

def test_expire_already_expired():
    t = HTask("t", "digit", "Q?", lease_s=1)
    t.expire(t.deadline)
    state1 = t.state
    t.expire(t.deadline + 100)
    assert t.state == state1  # no change

def test_expire_already_answered():
    t = HTask("t", "digit", "Q?")
    t.display()
    t.acknowledge()
    t.answer_task("42")
    t.expire(t.deadline + 1000)  # way past deadline
    assert t.state == "answered"  # terminal, not expired

def test_custom_safe_default():
    t = HTask("t", "digit", "Q?", safe_default="approve", lease_s=1)
    t.expire(t.deadline)
    assert t.answer["value"] == "approve"

def test_campaign_and_lane_fields():
    t = HTask("t", "confirm", "Go?", campaign="demo", lane="creds-first")
    v = t.view()
    assert v["campaign"] == "demo"
    assert v["lane"] == "creds-first"

def test_context_hash_binding():
    t = HTask("t", "confirm", "Go?", action={"amount": 10})
    assert t.verify_binding()

def test_context_hash_tamper_detected():
    t = HTask("t", "confirm", "Go?", action={"amount": 10})
    record = t.to_record()
    record["action"]["amount"] = 99  # tamper
    with pytest.raises(ValueError, match="binding"):
        HTask.from_record(record)


# ── HQueue operations ──────────────────────────────────────────────────

def test_queue_emit_and_active():
    q = HQueue()
    t1 = HTask("1", "digit", "Q1?")
    t2 = HTask("2", "confirm", "Q2?")
    q.emit(t1)
    q.emit(t2)
    assert q.active() is None  # both emitted
    t1.display()
    assert q.active().task_id == "1"

def test_queue_pending_count():
    q = HQueue()
    for i in range(5):
        q.emit(HTask(str(i), "digit", f"Q{i}?"))
    assert q.pending_count() == 5
    q.tasks["0"].display()
    assert q.pending_count() == 5  # displayed still counts
    q.tasks["0"].answer_task("0")
    assert q.pending_count() == 4  # answered removed

def test_queue_duplicate_rejects():
    q = HQueue()
    q.emit(HTask("1", "digit", "Q?"))
    with pytest.raises(ValueError, match="duplicate"):
        q.emit(HTask("1", "digit", "Q?"))

def test_queue_sweep_expires():
    q = HQueue()
    q.emit(HTask("1", "digit", "Q?", lease_s=1))
    q.emit(HTask("2", "confirm", "Q?", lease_s=10000))
    expired = q.sweep(now=int(time.time()) + 5)
    assert "1" in expired
    assert "2" not in expired

def test_queue_save_and_load():
    with tempfile.TemporaryDirectory() as d:
        q = HQueue()
        q.emit(HTask("1", "digit", "Q1?"))
        q.emit(HTask("2", "confirm", "Q2?"))
        q.tasks["1"].display()
        path = os.path.join(d, "queue.json")
        q.save(path)
        q2 = HQueue.load(path)
        assert len(q2.tasks) == 2
        assert q2.tasks["1"].state == "displayed"
        assert q2.tasks["2"].state == "emitted"

def test_queue_load_with_expired():
    with tempfile.TemporaryDirectory() as d:
        q = HQueue()
        q.emit(HTask("1", "digit", "Q?", lease_s=1))
        path = os.path.join(d, "queue.json")
        q.save(path)
        time.sleep(1.1)
        q2 = HQueue.load(path)  # sweep runs on load
        assert q2.tasks["1"].state == "expired"


# ── Harness parse_tool ─────────────────────────────────────────────────

def test_parse_tool_simple():
    r = parse_tool("TOOL: probe weak-creds-01")
    assert r == ("probe", ["weak-creds-01"])

def test_parse_tool_multi_arg():
    r = parse_tool("TOOL: try-creds weak-creds-01 admin admin")
    assert r == ("try-creds", ["weak-creds-01", "admin", "admin"])

def test_parse_tool_sqli_payload_with_spaces():
    r = parse_tool("TOOL: sqli sqli-sim-01 ' OR '1'='1")
    assert r is not None
    assert r[0] == "sqli"
    assert r[1][0] == "sqli-sim-01"

def test_parse_tool_submit():
    r = parse_tool("TOOL: submit weak-creds-01 XMCTF{weak_creds_demo_01}")
    assert r == ("submit", ["weak-creds-01", "XMCTF{weak_creds_demo_01}"])

def test_parse_tool_no_match():
    assert parse_tool("This is just regular text") is None

def test_parse_tool_alias():
    r = parse_tool("TOOL: try_creds weak-creds-01 admin admin")
    assert r[0] == "try-creds"  # aliased

def test_parse_tool_alias_read_file():
    r = parse_tool("TOOL: read_file traversal-01 ../../flag.txt")
    assert r[0] == "read-file"

def test_parse_tool_alias_submit_flag():
    r = parse_tool("TOOL: submit_flag weak-creds-01 XMCTF{test}")
    assert r[0] == "submit"

def test_parse_tool_extra_whitespace():
    r = parse_tool("TOOL:   probe   weak-creds-01")
    assert r == ("probe", ["weak-creds-01"])

def test_parse_tool_in_sentence():
    r = parse_tool("I'll try probing first.\nTOOL: probe weak-creds-01")
    assert r == ("probe", ["weak-creds-01"])
