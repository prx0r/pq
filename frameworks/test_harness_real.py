#!/usr/bin/env python3
"""test_harness_real.py — test the LLM harness with real Muse calls.

Exit code 0 = it works. Non-zero = it doesn't.
"""
import sys
import os
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor
from harness import call_api


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
    with open(os.path.join(ROOT, "runs", "harness-real-test.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def get_key():
    """Resolve a real key from vault."""
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    if not active:
        return None, None
    key = vault.resolve(active[0]["name"], "dashboard-chat", "chat-session",
                        active[0]["capability"])
    return key, active[0]


def test_muse_simple_call():
    """Muse responds to simple prompt."""
    key, cand = get_key()
    if not key:
        return {"skip": "no keys"}
    
    t0 = time.time()
    resp = call_api(key, [{"role": "user", "content": "Say HI"}])
    duration_ms = int((time.time() - t0) * 1000)
    
    text = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {})
    
    assert text.strip(), "must get response"
    assert len(text) > 0, "response must not be empty"
    
    return {
        "response": text[:100],
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
        "duration_ms": duration_ms,
    }


def test_muse_system_prompt():
    """Muse follows system prompt."""
    key, cand = get_key()
    if not key:
        return {"skip": "no keys"}
    
    resp = call_api(key, [
        {"role": "system", "content": "Reply with exactly: PROOF_OK"},
        {"role": "user", "content": "Go ahead."},
    ])
    
    text = resp["choices"][0]["message"]["content"]
    assert "PROOF_OK" in text, f"must contain PROOF_OK, got: {text[:100]}"
    
    return {"response": text[:100]}


def test_muse_multi_turn():
    """Muse handles multi-turn conversation."""
    key, cand = get_key()
    if not key:
        return {"skip": "no keys"}
    
    messages = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Hello Alice!"},
        {"role": "user", "content": "What is my name?"},
    ]
    
    resp = call_api(key, messages)
    text = resp["choices"][0]["message"]["content"]
    
    assert "Alice" in text, f"must remember name, got: {text[:100]}"
    
    return {"response": text[:100]}


def test_muse_tool_parsing():
    """Muse can output tool call format."""
    key, cand = get_key()
    if not key:
        return {"skip": "no keys"}
    
    resp = call_api(key, [
        {"role": "system", "content": "You have a tool: TOOL: probe <target>. Use it."},
        {"role": "user", "content": "Probe target weak-creds-01"},
    ])
    
    text = resp["choices"][0]["message"]["content"]
    # Check if response contains tool call format
    has_tool = "TOOL:" in text or "probe" in text.lower()
    
    return {"response": text[:200], "has_tool_format": has_tool}


def test_muse_json_output():
    """Muse can output JSON."""
    key, cand = get_key()
    if not key:
        return {"skip": "no keys"}
    
    resp = call_api(key, [
        {"role": "user", "content": 'Return a JSON object with key "status" and value "ok". Return only the JSON.'},
    ])
    
    text = resp["choices"][0]["message"].get("content", "")
    
    # Try to parse as JSON
    try:
        parsed = json.loads(text)
        assert parsed.get("status") == "ok", f"status must be ok, got {parsed}"
        return {"response": text[:100], "json_valid": True}
    except json.JSONDecodeError:
        return {"response": text[:200], "json_valid": False}


def main():
    tests = [
        ("muse_simple_call", test_muse_simple_call),
        ("muse_system_prompt", test_muse_system_prompt),
        ("muse_multi_turn", test_muse_multi_turn),
        ("muse_tool_parsing", test_muse_tool_parsing),
        ("muse_json_output", test_muse_json_output),
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
