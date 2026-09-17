"""Pi/ACP runtime configuration.

The kernel remains usable without ACP installed. When ACP is requested we require
the official `agent-client-protocol` package rather than implementing JSON-RPC
framing ourselves.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class PiRuntimeConfig:
    command: str = "pi"
    acp_adapter: str = "pi-acp"
    model: str = ""
    mode: str = "raw"
    cwd: str = ""

    def validate(self, *, require_acp: bool = False) -> None:
        if not self.model:
            raise ValueError("model is required; silent fallback is forbidden")
        if self.mode not in {"raw", "tools", "agentcom", "redteam"}:
            raise ValueError(f"unsupported Pi mode: {self.mode}")
        if require_acp:
            if importlib.util.find_spec("acp") is None:
                raise RuntimeError("ACP requested but agent-client-protocol is not installed")
            if not shutil.which(self.acp_adapter) and not os.path.exists(self.acp_adapter):
                raise RuntimeError(f"ACP adapter not found: {self.acp_adapter}")

    def argv(self) -> list[str]:
        self.validate(require_acp=False)
        return [self.command, "--model", self.model]
