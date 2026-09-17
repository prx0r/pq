"""Trusted broker around the existing pq Vault.

The broker hides bearer capability handles from model-facing discovery and
supports quarantine for secrets discovered during scans/CTFs.
"""
from __future__ import annotations

import secrets
from typing import Callable, Any


class VaultBroker:
    def __init__(self, vault):
        self.vault = vault

    def model_view(self, *, kind: str = "", tier: str = "", provider: str = "") -> list[dict]:
        out = []
        for item in self.vault.find(kind=kind, tier=tier, provider=provider):
            item = dict(item)
            item.pop("capability", None)
            item["available"] = self.vault.credential_available(item["name"])
            out.append(item)
        return out

    def credential_available(self, name: str) -> bool:
        return bool(self.vault.credential_available(name))

    def _capability(self, name: str) -> str:
        # Trusted process only. Never serialize this value into model context.
        raw = self.vault.secrets.get(name)
        if not raw:
            raise ValueError("unknown secret")
        return raw["capability"]

    def with_secret(self, name: str, *, tool: str, worker: str, scope: str = "", callback: Callable[[str], Any]):
        value = self.vault.resolve(name, tool, worker, self._capability(name), scope=scope)
        return callback(value)

    def quarantine(self, name: str, value: str, *, kind: str = "other", ttl_s: int = 86400) -> dict:
        qname = f"quarantine:{name}:{secrets.token_hex(4)}"
        return self.vault.store(
            qname,
            value,
            allowed_tools=[],
            allowed_workers=[],
            scope="quarantine",
            ttl_s=ttl_s,
            max_uses=0,
            kind=kind,
            tier="unpaid",
            active=False,
        )

    def promote(self, quarantined_name: str, *, allowed_tools: list[str], allowed_workers: list[str], scope: str = "", ttl_s: int = 3600, max_uses: int = 1) -> dict:
        s = self.vault.secrets.get(quarantined_name)
        if not s or s.get("active", True):
            raise ValueError("not a quarantined secret")
        try:
            plaintext = self.vault.fernet.decrypt(s["cipher"].encode()).decode()
        except Exception as exc:
            raise ValueError("cannot decrypt quarantined secret") from exc
        # Create a fresh capability rather than reactivating the quarantine record.
        promoted = self.vault.store(
            quarantined_name.replace("quarantine:", "approved:", 1),
            plaintext,
            allowed_tools=allowed_tools,
            allowed_workers=allowed_workers,
            scope=scope,
            ttl_s=ttl_s,
            max_uses=max_uses,
            kind=s.get("kind", "other"),
            tier=s.get("tier", "unpaid"),
            active=True,
            rate_limit=s.get("rate_limit", {}),
            model=s.get("model", ""),
            provider=s.get("provider", ""),
        )
        return promoted
