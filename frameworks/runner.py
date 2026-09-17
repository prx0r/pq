"""Framework test runner — shared utilities for all framework tests.

Every test:
1. Resolves a vault-held key
2. Calls Muse via the same harness as pq
3. Logs usage to runs/framework-*.jsonl
4. Asserts the response meets criteria
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.vault.asynclog import UsageLogger
from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor
import pqconfig as cfg

BACKEND = os.environ.get("PQ_MODEL", "muse-spark-1.3-contributor")
RUNS_DIR = os.path.join(ROOT, "runs")


def get_vault():
    """Get vault instance."""
    return Vault(os.path.expanduser("~/.qpbot/vault.json"))


def get_key(vault):
    """Resolve an active LLM key from vault."""
    active = vault.find(kind="llm-inference", tier="paid")
    if not active:
        return None, None
    ordered = sorted(active, key=lambda a: 0 if a.get("model") == BACKEND else 1)
    for cand in ordered:
        try:
            key = vault.resolve(cand["name"], "dashboard-chat",
                                "chat-session", cand["capability"])
            return key, cand
        except ValueError:
            continue
    return None, None


def call_muse(key: str, messages: list[dict], model: str = None, retries: int = 2) -> dict:
    """Call Muse backend with messages. Returns response dict.

    Uses the Responses API for muse-spark models (chat/completions returns 403).
    Retries on empty responses.
    """
    import uuid
    model = model or BACKEND
    api_base = os.environ.get("PQ_API", "https://opencode.ai/zen/go/v1")

    for attempt in range(retries + 1):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "x-opencode-session": str(uuid.uuid4()),
            "User-Agent": "pq-framework/0.1",
        }

        if model.startswith("muse-spark"):
            # Muse Spark uses Responses API, not chat/completions
            url = f"{api_base}/responses"
            input_items = []
            for m in messages:
                role = m.get("role", "user")
                if role not in ("user", "assistant", "system"):
                    role = "user"
                input_items.append({"role": role, "content": str(m.get("content", ""))})

            body = json.dumps({
                "model": model,
                "input": input_items,
                "stream": False,
                "max_output_tokens": 1024,
            }).encode()

            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read())

            # Normalize to chat shape
            parts = []
            for item in raw.get("output", []):
                for c in item.get("content", []):
                    if c.get("type") == "output_text" and c.get("text"):
                        parts.append(c["text"])
            text = "".join(parts) or raw.get("output_text", "")

            usage = raw.get("usage", {})
            result = {
                "choices": [{"message": {"content": text}}],
                "usage": {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                },
                "model": raw.get("model", model),
            }
        else:
            # Non-Muse models use chat/completions
            url = f"{api_base}/chat/completions"
            body = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 1024,
            }).encode()

            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())

        # Check for empty response and retry
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if text.strip() or attempt == retries:
            return result

        time.sleep(1)  # Wait before retry

    return result


def log_framework_event(framework: str, event: dict):
    """Append a JSONL event to runs/framework-{framework}.jsonl."""
    os.makedirs(RUNS_DIR, exist_ok=True)
    path = os.path.join(RUNS_DIR, f"framework-{framework}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def make_run_id():
    """Generate a run ID."""
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def framework_test(framework: str):
    """Decorator for framework tests. Handles vault, logging, timing."""
    def decorator(func):
        def wrapper():
            run_id = make_run_id()
            vault = get_vault()
            key, cand = get_key(vault)
            if key is None:
                import pytest
                pytest.skip(f"no active LLM keys for {framework} test")

            logger = UsageLogger(
                vault=vault,
                log_path=os.path.join(RUNS_DIR, "llm-runs.jsonl"),
                buffer_size=100,
                flush_interval_s=1,
            )

            t0 = time.time()
            try:
                result = func(key=key, run_id=run_id)
                duration_ms = int((time.time() - t0) * 1000)

                # Log success
                log_framework_event(framework, {
                    "run_id": run_id,
                    "test": func.__name__,
                    "status": "PASS",
                    "duration_ms": duration_ms,
                    "result": result,
                })

                return result

            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                log_framework_event(framework, {
                    "run_id": run_id,
                    "test": func.__name__,
                    "status": "FAIL",
                    "duration_ms": duration_ms,
                    "error": str(e),
                })
                raise

            finally:
                # Log usage
                if cand:
                    logger.log(
                        cand["name"],
                        BACKEND,
                        tokens_in=0,  # estimated
                        tokens_out=0,
                        cost_minor=0,
                        duration_ms=duration_ms,
                        run_id=run_id,
                    )
                logger.shutdown()

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
