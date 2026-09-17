"""Manual model/provider selection with request inspection.

No automatic provider fallback. The caller chooses a provider/model explicitly.
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    model: str
    secret_name: str = ""
    require_tee: bool = False
    require_attestation: bool = False
    e2ee: bool = False
    proxy: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


class ProviderRegistry:
    def __init__(self, providers: dict[str, ProviderConfig] | None = None):
        self.providers = providers or {}

    @classmethod
    def load(cls, path: str) -> "ProviderRegistry":
        raw = json.loads(Path(path).read_text())
        return cls({k: ProviderConfig(name=k, **v) for k, v in raw.get("providers", {}).items()})

    def get(self, name: str) -> ProviderConfig:
        if name not in self.providers:
            raise KeyError(f"unknown provider {name}")
        return self.providers[name]

    def add(self, cfg: ProviderConfig) -> None:
        self.providers[cfg.name] = cfg

    def public_view(self, name: str) -> dict[str, Any]:
        return asdict(self.get(name))


def build_chat_request(cfg: ProviderConfig, messages: list[dict], *, system_prompt: str = "", tools: list[dict] | None = None) -> dict:
    out_messages = []
    if system_prompt:
        out_messages.append({"role": "system", "content": system_prompt})
    out_messages.extend(copy.deepcopy(messages))
    body: dict[str, Any] = {"model": cfg.model, "messages": out_messages}
    if tools:
        body["tools"] = copy.deepcopy(tools)
    return body


def inspect_request(cfg: ProviderConfig, body: dict, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    safe_headers = {}
    for k, v in (headers or {}).items():
        safe_headers[k] = "[REDACTED]" if k.lower() in {"authorization", "x-api-key", "api-key"} else v
    return {
        "provider": cfg.name,
        "endpoint": cfg.base_url.rstrip("/") + "/chat/completions",
        "model": cfg.model,
        "privacy": {
            "require_tee": cfg.require_tee,
            "require_attestation": cfg.require_attestation,
            "e2ee": cfg.e2ee,
            "proxy": cfg.proxy,
        },
        "headers": safe_headers,
        "body": copy.deepcopy(body),
    }
