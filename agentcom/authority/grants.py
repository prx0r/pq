"""Production authority grants for consequential agent actions.

Design rules:
- budgets are not authority
- the worker cannot self-authorize
- grants are bound to a canonical action digest
- verification uses one configured trust root; grants never carry trust keys
- use counters are consumed atomically in SQLite immediately before effect
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class AuthorityAction:
    capability: str
    subject: str
    resource: str
    params: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    contract_root: str = ""
    policy_version: str = ""
    value_minor: int = 0
    currency: str = ""
    recipient: str = ""

    def __post_init__(self):
        if not self.capability or not self.subject or not self.resource:
            raise ValueError("capability, subject and resource are required")
        if self.value_minor < 0:
            raise ValueError("value_minor must be >= 0")

    def body(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_hex(self.body())


@dataclass(frozen=True)
class Grant:
    grant_id: str
    action_digest: str
    subject: str
    capability: str
    issued_at: int
    not_before: int
    expires_at: int
    max_uses: int
    max_value_minor: int
    currency: str
    signature: str

    def signed_body(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        return d

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Grant":
        return cls(**raw)


class GrantVerifier:
    """Verifier anchored to one local trust root."""

    def __init__(self, public_key: Ed25519PublicKey):
        self.public_key = public_key

    @classmethod
    def from_public_bytes(cls, raw: bytes) -> "GrantVerifier":
        return cls(Ed25519PublicKey.from_public_bytes(raw))

    def public_bytes(self) -> bytes:
        return self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def verify(self, grant: Grant, action: AuthorityAction, now: int | None = None) -> None:
        now = int(time.time()) if now is None else int(now)
        if grant.action_digest != action.digest:
            raise ValueError("grant/action digest mismatch")
        if grant.subject != action.subject or grant.capability != action.capability:
            raise ValueError("grant subject/capability mismatch")
        if now < grant.not_before:
            raise ValueError("grant not active yet")
        if now >= grant.expires_at:
            raise ValueError("grant expired")
        if grant.max_uses < 1:
            raise ValueError("invalid max_uses")
        if grant.max_value_minor and action.value_minor > grant.max_value_minor:
            raise ValueError("grant value ceiling exceeded")
        if grant.currency and action.currency and grant.currency != action.currency:
            raise ValueError("grant currency mismatch")
        try:
            sig = base64.urlsafe_b64decode(grant.signature.encode("ascii"))
            self.public_key.verify(sig, canonical_json(grant.signed_body()))
        except Exception as exc:  # cryptography intentionally gives sparse errors
            raise ValueError("invalid grant signature") from exc


class GrantStore:
    """Atomic use-counter store. SQLite serializes concurrent consumption."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db().executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS grants (
                grant_id TEXT PRIMARY KEY,
                action_digest TEXT NOT NULL,
                max_uses INTEGER NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            """
        )

    def _db(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    def register(self, grant: Grant) -> None:
        with self._db() as con:
            con.execute(
                "INSERT OR IGNORE INTO grants(grant_id,action_digest,max_uses,uses,expires_at,revoked,created_at) VALUES(?,?,?,?,?,?,?)",
                (grant.grant_id, grant.action_digest, grant.max_uses, 0, grant.expires_at, 0, grant.issued_at),
            )

    def consume(self, grant: Grant, action: AuthorityAction, verifier: GrantVerifier, now: int | None = None) -> int:
        now = int(time.time()) if now is None else int(now)
        verifier.verify(grant, action, now=now)
        con = self._db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM grants WHERE grant_id=?", (grant.grant_id,)).fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO grants(grant_id,action_digest,max_uses,uses,expires_at,revoked,created_at) VALUES(?,?,?,?,?,?,?)",
                    (grant.grant_id, grant.action_digest, grant.max_uses, 0, grant.expires_at, 0, grant.issued_at),
                )
                row = con.execute("SELECT * FROM grants WHERE grant_id=?", (grant.grant_id,)).fetchone()
            if row["action_digest"] != action.digest:
                raise ValueError("stored grant digest mismatch")
            if row["revoked"]:
                raise ValueError("grant revoked")
            if now >= int(row["expires_at"]):
                raise ValueError("grant expired")
            if int(row["uses"]) >= int(row["max_uses"]):
                raise ValueError("grant usage exhausted")
            uses = int(row["uses"]) + 1
            con.execute("UPDATE grants SET uses=? WHERE grant_id=?", (uses, grant.grant_id))
            con.execute("COMMIT")
            return uses
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    def revoke(self, grant_id: str) -> None:
        with self._db() as con:
            con.execute("UPDATE grants SET revoked=1 WHERE grant_id=?", (grant_id,))

    def status(self, grant_id: str) -> dict[str, Any] | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
            return dict(row) if row else None


class GrantAuthority:
    """Trusted grant minting service. Private key remains local to this process."""

    def __init__(self, private_key: Ed25519PrivateKey, store: GrantStore):
        self.private_key = private_key
        self.store = store
        self.verifier = GrantVerifier(private_key.public_key())

    @classmethod
    def load_or_create(cls, key_path: str, store_path: str) -> "GrantAuthority":
        p = Path(key_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            private_key = Ed25519PrivateKey.from_private_bytes(p.read_bytes())
        else:
            private_key = Ed25519PrivateKey.generate()
            raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
        return cls(private_key, GrantStore(store_path))

    def issue(
        self,
        action: AuthorityAction,
        *,
        max_uses: int = 1,
        ttl_s: int = 300,
        not_before: int | None = None,
        max_value_minor: int | None = None,
        now: int | None = None,
    ) -> Grant:
        now = int(time.time()) if now is None else int(now)
        if max_uses < 1:
            raise ValueError("max_uses must be >= 1")
        if ttl_s < 1:
            raise ValueError("ttl_s must be >= 1")
        ceiling = action.value_minor if max_value_minor is None else int(max_value_minor)
        if ceiling < action.value_minor:
            raise ValueError("grant ceiling cannot be below proposed action value")
        unsigned = {
            "grant_id": str(uuid.uuid4()),
            "action_digest": action.digest,
            "subject": action.subject,
            "capability": action.capability,
            "issued_at": now,
            "not_before": now if not_before is None else int(not_before),
            "expires_at": now + int(ttl_s),
            "max_uses": int(max_uses),
            "max_value_minor": ceiling,
            "currency": action.currency,
        }
        sig = self.private_key.sign(canonical_json(unsigned))
        grant = Grant(**unsigned, signature=base64.urlsafe_b64encode(sig).decode("ascii"))
        self.store.register(grant)
        return grant
