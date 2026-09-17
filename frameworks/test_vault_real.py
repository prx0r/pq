#!/usr/bin/env python3
"""test_vault_real.py — test vault with real key resolution and API calls.

Exit code 0 = it works. Non-zero = it doesn't.
"""
import sys
import os
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.vault.store import Vault


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
    with open(os.path.join(ROOT, "runs", "vault-real-test.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def test_vault_find_keys():
    """Vault finds LLM keys."""
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    
    assert len(active) > 0, "must find at least 1 key"
    assert active[0]["name"], "key must have name"
    assert active[0]["capability"], "key must have capability"
    
    return {"key_count": len(active), "first_key": active[0]["name"]}


def test_vault_resolve_key():
    """Vault resolves a real key."""
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    
    key = vault.resolve(active[0]["name"], "dashboard-chat", "chat-session",
                        active[0]["capability"])
    
    assert key is not None, "key must resolve"
    assert len(key) > 10, "key must be meaningful"
    assert key.startswith("sk-"), "key must start with sk-"
    
    return {"key_prefix": key[:15] + "..."}


def test_vault_resolve_wrong_capability():
    """Vault rejects wrong capability."""
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    
    try:
        vault.resolve(active[0]["name"], "wrong-tool", "w", "bad_cap")
        assert False, "must raise ValueError"
    except ValueError:
        pass
    
    return {"rejected": True}


def test_vault_usage_tracking():
    """Vault tracks usage."""
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    usage = vault.usage_summary()
    
    assert "totals" in usage, "usage must have totals"
    
    return {"usage": usage}


def main():
    tests = [
        ("vault_find_keys", test_vault_find_keys),
        ("vault_resolve_key", test_vault_resolve_key),
        ("vault_resolve_wrong_capability", test_vault_resolve_wrong_capability),
        ("vault_usage_tracking", test_vault_usage_tracking),
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
