"""Vault — local encrypted secret store with scoped capability grants.

Model sees credential_available(name) only. Tools resolve values through
grants bound to tool + worker + scope + expiry + usage cap. Every access
appends to the audit log. Master key: QPBOT_VAULT_KEY env or 0600 key file.

Categories organize secrets for agent retrieval:
  kind: llm-inference | cloudflare | service | other
  tier: paid | unpaid | trial
  active: bool — quick filter for "give me a working key"
  rate_limit: {per_minute, per_day, monthly_cap} — known limits
  usage: {calls, tokens_in, tokens_out, cost_minor} — deterministic counter
"""
from __future__ import annotations

import base64
import json
import os
import time

from cryptography.fernet import Fernet, InvalidToken


def _master_key(key_path: str) -> bytes:
    env = os.environ.get("QPBOT_VAULT_KEY", "")
    if env:
        return env.encode()
    if os.path.exists(key_path):
        return open(key_path, "rb").read().strip()
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key + b"\n")
    return key


class Vault:
    def __init__(self, store_path: str, key_path: str = ""):
        self.store_path = store_path
        self.fernet = Fernet(_master_key(
            key_path or os.path.join(os.path.dirname(store_path) or ".",
                                     "vault.key")))
        self._load()

    def _load(self):
        self.secrets: dict[str, dict] = {}
        self.audit: list[dict] = []
        if os.path.exists(self.store_path):
            raw = json.load(open(self.store_path))
            self.audit = raw.get("audit", [])
            for name, s in raw.get("secrets", {}).items():
                self.secrets[name] = s

    def _save(self):
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        json.dump({"secrets": self.secrets, "audit": self.audit},
                  open(self.store_path, "w"), indent=1)

    def _log(self, event: str, **fields):
        self.audit.append({"ts": int(time.time()), "event": event, **fields})

    def store(self, name: str, value: str, allowed_tools: list[str],
              allowed_workers: list[str], scope: str = "",
              ttl_s: int = 3600, max_uses: int = 0, *,
              kind: str = "other", tier: str = "unpaid",
              active: bool = True, rate_limit: dict | None = None,
              model: str = "", provider: str = "") -> dict:
        """Deposit from the H-task rail. Plaintext never leaves this call."""
        token = base64.urlsafe_b64encode(os.urandom(18)).decode()
        self.secrets[name] = {
            "cipher": self.fernet.encrypt(value.encode()).decode(),
            "allowed_tools": allowed_tools,
            "allowed_workers": allowed_workers,
            "scope": scope,
            "expires": int(time.time()) + ttl_s,
            "max_uses": max_uses,
            "uses": 0,
            "capability": token,
            "kind": kind,
            "tier": tier,
            "active": active,
            "model": model,
            "provider": provider,
            "rate_limit": rate_limit or {},
            "usage": {"calls": 0, "tokens_in": 0, "tokens_out": 0,
                      "cost_minor": 0},
        }
        self._log("stored", name=name, scope=scope, ttl_s=ttl_s,
                  kind=kind, tier=tier)
        self._save()
        return {"name": name, "stored": True, "expires_in_s": ttl_s}

    def credential_available(self, name: str) -> bool:
        """The only thing the model may see. False when expired, inactive,
        or the usage cap is spent — exhausted keys are never offered."""
        s = self.secrets.get(name)
        if not s:
            return False
        if s["expires"] <= time.time():
            return False
        if not s.get("active", True):
            return False
        if s.get("max_uses") and s.get("uses", 0) >= s["max_uses"]:
            return False
        return True

    def resolve(self, name: str, tool: str, worker: str,
                capability: str, scope: str = "") -> str:
        """Protected channel: value out only on full grant match."""
        s = self.secrets.get(name)
        if not s:
            raise ValueError("unknown secret")
        if not s.get("active", True):
            raise ValueError("key inactive")
        if s["capability"] != capability:
            raise ValueError("capability mismatch")
        if tool not in s["allowed_tools"]:
            raise ValueError(f"tool {tool} not granted")
        if worker not in s["allowed_workers"]:
            raise ValueError(f"worker {worker} not granted")
        if scope and s["scope"] and scope != s["scope"]:
            raise ValueError("scope mismatch")
        if s["expires"] <= time.time():
            raise ValueError("grant expired")
        if s["max_uses"] and s["uses"] >= s["max_uses"]:
            raise ValueError("usage cap reached")
        s["uses"] += 1
        self._log("resolved", name=name, tool=tool, worker=worker,
                  uses=s["uses"])
        self._save()
        try:
            return self.fernet.decrypt(s["cipher"].encode()).decode()
        except InvalidToken:
            raise ValueError("vault key mismatch")

    def record_usage(self, name: str, tokens_in: int = 0,
                     tokens_out: int = 0, cost_minor: int = 0):
        """Deterministic usage counter. Called after every API call."""
        s = self.secrets.get(name)
        if not s:
            return
        u = s.setdefault("usage", {"calls": 0, "tokens_in": 0,
                                   "tokens_out": 0, "cost_minor": 0})
        u["calls"] += 1
        u["tokens_in"] += tokens_in
        u["tokens_out"] += tokens_out
        u["cost_minor"] += cost_minor
        self._log("usage", name=name, tokens_in=tokens_in,
                  tokens_out=tokens_out, cost_minor=cost_minor,
                  total_calls=u["calls"])
        self._save()

    def set_active(self, name: str, active: bool):
        s = self.secrets.get(name)
        if s:
            s["active"] = active
            self._log("active_set", name=name, active=active)
            self._save()

    def find(self, kind: str = "", tier: str = "", active_only: bool = True,
             provider: str = "") -> list[dict]:
        """Agent query: find matching keys without resolving values.
        With active_only, spent/expired/inactive keys are filtered out."""
        out = []
        for name, s in self.secrets.items():
            if active_only and not self.credential_available(name):
                continue
            if kind and s.get("kind") != kind:
                continue
            if tier and s.get("tier") != tier:
                continue
            if provider and s.get("provider") != provider:
                continue
            out.append({"name": name, "kind": s.get("kind", "other"),
                        "tier": s.get("tier", "unpaid"),
                        "provider": s.get("provider", ""),
                        "model": s.get("model", ""),
                        "usage": s.get("usage", {}),
                        "rate_limit": s.get("rate_limit", {}),
                        "capability": s.get("capability", "")})
        return out

    def usage_summary(self) -> dict:
        totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_minor": 0}
        by_kind: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        for name, s in self.secrets.items():
            u = s.get("usage", {})
            kind = s.get("kind", "other")
            model = s.get("model", "unknown")
            for k in ("calls", "tokens_in", "tokens_out", "cost_minor"):
                totals[k] += u.get(k, 0)
                by_kind.setdefault(kind, {}).setdefault(k, 0)
                by_kind[kind][k] += u.get(k, 0)
                by_model.setdefault(model, {}).setdefault(k, 0)
                by_model[model][k] += u.get(k, 0)
        return {"totals": totals, "by_kind": by_kind, "by_model": by_model}

    def revoke(self, name: str):
        if name in self.secrets:
            del self.secrets[name]
            self._log("revoked", name=name)
            self._save()
