#!/usr/bin/env python3
"""test_arena_real.py — test arena with real tool calls.

Exit code 0 = it works. Non-zero = it doesn't.
"""
import sys
import os
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.arena import submit_flag, probe, try_creds, read_file, exploit_sqli_sim, is_allowed


def log_result(test_name, passed, details=None):
    run_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    entry = {
        "run_id": run_id,
        "test": test_name,
        "passed": passed,
        "timestamp": time.time(),
    }
    if details:
        entry["details"] = details
    os.makedirs(os.path.join(ROOT, "runs"), exist_ok=True)
    with open(os.path.join(ROOT, "runs", "arena-real-test.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def test_probe_target():
    """Probe returns banner and category."""
    result = probe("weak-creds-01")
    
    assert "banner" in result or "category" in result, f"must have banner/category: {result}"
    
    return {"result": result}


def test_try_creds_correct():
    """Correct creds capture flag."""
    result = try_creds("weak-creds-01", "admin", "admin")
    
    assert result.get("captured") is True or result.get("ok") is True, f"must capture: {result}"
    
    return {"result": result}


def test_try_creds_wrong():
    """Wrong creds fail."""
    result = try_creds("weak-creds-01", "wrong", "wrong")
    
    assert result.get("captured") is not True, "must not capture with wrong creds"
    
    return {"result": result}


def test_submit_correct_flag():
    """Correct flag is captured."""
    result = submit_flag("weak-creds-01", "XMCTF{weak_creds_demo_01}")
    
    assert result["verdict"] == "CAPTURED", f"must be CAPTURED, got {result['verdict']}"
    assert result["flag_sha256"], "must have flag hash"
    
    return {"verdict": result["verdict"], "flag_sha256": result["flag_sha256"][:16] + "..."}


def test_submit_wrong_flag():
    """Wrong flag is rejected."""
    result = submit_flag("weak-creds-01", "WRONG_FLAG")
    
    assert result["verdict"] == "REJECTED", f"must be REJECTED, got {result['verdict']}"
    
    return {"verdict": result["verdict"]}


def test_submit_unknown_target():
    """Unknown target returns UNKNOWN_TARGET."""
    result = submit_flag("nonexistent", "XMCTF{anything}")
    
    assert result["verdict"] == "UNKNOWN_TARGET", f"must be UNKNOWN_TARGET, got {result['verdict']}"
    
    return {"verdict": result["verdict"]}


def test_tool_grants():
    """Tool grant table works."""
    assert is_allowed("probe") is True
    assert is_allowed("try_creds") is True
    assert is_allowed("read_file") is True
    assert is_allowed("exploit_sqli_sim") is True
    assert is_allowed("submit_flag") is True
    assert is_allowed("reverse_shell") is False
    assert is_allowed("nonexistent") is False
    
    return {"allowed": ["probe", "try_creds", "read_file", "exploit_sqli_sim", "submit_flag"],
            "denied": ["reverse_shell", "nonexistent"]}


def test_full_attack_chain():
    """Full chain: probe → try creds → submit flag."""
    # 1. Probe
    probe_result = probe("weak-creds-01")
    assert probe_result, "probe must return result"
    
    # 2. Try creds
    creds_result = try_creds("weak-creds-01", "admin", "admin")
    assert creds_result.get("captured") is True, "creds must capture"
    
    # 3. Submit flag
    flag_result = submit_flag("weak-creds-01", "XMCTF{weak_creds_demo_01}")
    assert flag_result["verdict"] == "CAPTURED", "flag must be captured"
    
    return {
        "probe_ok": bool(probe_result),
        "creds_captured": creds_result.get("captured"),
        "flag_verdict": flag_result["verdict"],
    }


def main():
    tests = [
        ("probe_target", test_probe_target),
        ("try_creds_correct", test_try_creds_correct),
        ("try_creds_wrong", test_try_creds_wrong),
        ("submit_correct_flag", test_submit_correct_flag),
        ("submit_wrong_flag", test_submit_wrong_flag),
        ("submit_unknown_target", test_submit_unknown_target),
        ("tool_grants", test_tool_grants),
        ("full_attack_chain", test_full_attack_chain),
    ]
    
    all_passed = True
    for name, fn in tests:
        try:
            details = fn()
            log_result(name, True, details)
            print(f"✓ {name}")
        except Exception as e:
            all_passed = False
            log_result(name, False, {"error": str(e)})
            print(f"✗ {name}: {e}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
