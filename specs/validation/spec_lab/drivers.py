from __future__ import annotations
from abc import ABC, abstractmethod
import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

class DriverError(RuntimeError):
    pass

class LLMDriver(ABC):
    @abstractmethod
    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

class RecordedDriver(LLMDriver):
    """Deterministic test driver.

    The recorded transcript is our stand-in for "the LLM" during offline
    architecture testing. It keeps LLM cognition outside the deterministic
    consequence kernel while making every experiment exactly replayable.
    """
    def __init__(self, responses: dict[str, Any] | str | Path):
        if isinstance(responses, (str, Path)):
            responses = json.loads(Path(responses).read_text(encoding="utf-8"))
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, *, stage: str, system: str, user: str, context=None) -> dict[str, Any]:
        self.calls.append({
            "stage": stage,
            "system": system,
            "user": user,
            "context": context or {},
        })
        if stage not in self.responses:
            raise DriverError(f"no recorded response for stage {stage}")
        # JSON round-trip gives callers an isolated copy.
        return json.loads(json.dumps(self.responses[stage]))


class LoggingDriver(LLMDriver):
    """Append every model request/response to JSONL for scientific replay."""
    def __init__(self, base: LLMDriver, log_path: str | Path):
        self.base=base
        self.log_path=Path(log_path)
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self.sequence=0

    def complete_json(self, *, stage: str, system: str, user: str, context=None) -> dict[str, Any]:
        self.sequence += 1
        request={
            "seq":self.sequence,"stage":stage,"system":system,
            "user":user,"context":context or {},
        }
        try:
            response=self.base.complete_json(stage=stage,system=system,user=user,context=context)
            row={**request,"ok":True,"response":response}
        except Exception as e:
            row={**request,"ok":False,"error":f"{type(e).__name__}: {e}"}
            with self.log_path.open("a",encoding="utf-8") as f:
                f.write(json.dumps(row,sort_keys=True)+"\\n")
            raise
        with self.log_path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(row,sort_keys=True)+"\\n")
        return response

class TransformDriver(LLMDriver):
    """Wrap another driver and mutate stage outputs to red-team validation."""
    def __init__(self, base: LLMDriver, transforms: dict[str, Any]):
        self.base = base
        self.transforms = transforms

    def complete_json(self, *, stage: str, system: str, user: str, context=None) -> dict[str, Any]:
        out = self.base.complete_json(stage=stage, system=system, user=user, context=context)
        fn = self.transforms.get(stage)
        return fn(out) if fn else out

class CommandDriver(LLMDriver):
    """Generic model/agent bridge.

    The command reads one JSON request on stdin and must emit exactly one JSON
    object on stdout. This makes the lab compatible with OpenCode, Hermes, a
    local model wrapper, or any future driver without adding it to the kernel.

    Request:
      {"stage","system","user","context"}

    Response:
      JSON object for that stage.
    """
    def __init__(self, command: str | list[str], *, timeout: int = 300, env: dict[str, str] | None = None):
        self.command = shlex.split(command) if isinstance(command, str) else list(command)
        self.timeout = timeout
        self.env = {**os.environ, **(env or {})}

    def complete_json(self, *, stage: str, system: str, user: str, context=None) -> dict[str, Any]:
        payload = json.dumps({
            "stage": stage,
            "system": system,
            "user": user,
            "context": context or {},
        })
        p = subprocess.run(
            self.command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=self.env,
        )
        if p.returncode != 0:
            raise DriverError(f"driver failed rc={p.returncode}: {p.stderr[-1000:]}")
        try:
            out = json.loads(p.stdout)
        except json.JSONDecodeError as e:
            raise DriverError(f"driver emitted invalid JSON: {e}") from e
        if not isinstance(out, dict):
            raise DriverError("driver response must be object")
        return out

class OpenAICompatibleDriver(LLMDriver):
    """Minimal OpenAI-compatible JSON driver using only the stdlib.

    This is deliberately configurable rather than hard-coding a provider.
    Point AGENTCOM_LLM_BASE_URL at an OpenAI-compatible endpoint (for example,
    a local gateway or an OpenCode-Go-compatible gateway if exposed that way).

    Environment:
      AGENTCOM_LLM_BASE_URL  e.g. https://.../v1
      AGENTCOM_LLM_API_KEY
      AGENTCOM_LLM_MODEL

    This adapter is outside the deterministic kernel and is expected to change.
    """
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: int = 300):
        self.base_url = (base_url or os.getenv("AGENTCOM_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("AGENTCOM_LLM_API_KEY", "")
        self.model = model or os.getenv("AGENTCOM_LLM_MODEL", "")
        self.timeout = timeout
        if not self.base_url or not self.model:
            raise DriverError("AGENTCOM_LLM_BASE_URL and AGENTCOM_LLM_MODEL required")

    def complete_json(self, *, stage: str, system: str, user: str, context=None) -> dict[str, Any]:
        # Provider-specific structured-output details intentionally stay here,
        # not in the core. We ask for one JSON object and reject anything else.
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user + "\n\nContext:\n" + json.dumps(context or {})},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read().decode())
        except Exception as e:
            raise DriverError(f"OpenAI-compatible request failed: {e}") from e
        try:
            text = payload["choices"][0]["message"]["content"]
            out = json.loads(text)
        except Exception as e:
            raise DriverError("provider response did not contain JSON object content") from e
        if not isinstance(out, dict):
            raise DriverError("provider output must be object")
        return out
