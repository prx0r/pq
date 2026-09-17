"""One-time out-of-band approval tokens.

Email is only a human-authentication channel. Redeeming a token does not execute
the action; it returns the bound action digest so trusted AgentCom code can mint
a normal authority grant.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from pathlib import Path


class ApprovalTokenStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS approval_tokens(
                    token_hash TEXT PRIMARY KEY,
                    action_digest TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER,
                    created_at INTEGER NOT NULL
                )"""
            )

    def _db(self):
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, action_digest: str, subject: str, ttl_s: int = 600, now: int | None = None) -> str:
        if not action_digest or not subject:
            raise ValueError("action_digest and subject required")
        now = int(time.time()) if now is None else int(now)
        token = secrets.token_urlsafe(32)
        with self._db() as con:
            con.execute(
                "INSERT INTO approval_tokens VALUES(?,?,?,?,NULL,?)",
                (self._hash(token), action_digest, subject, now + int(ttl_s), now),
            )
        return token

    def claim(self, token: str, now: int | None = None) -> dict:
        now = int(time.time()) if now is None else int(now)
        h = self._hash(token)
        con = self._db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM approval_tokens WHERE token_hash=?", (h,)).fetchone()
            if row is None:
                raise ValueError("unknown approval token")
            if row["consumed_at"] is not None:
                raise ValueError("approval token already consumed")
            if now >= int(row["expires_at"]):
                raise ValueError("approval token expired")
            con.execute("UPDATE approval_tokens SET consumed_at=? WHERE token_hash=?", (now, h))
            con.execute("COMMIT")
            return {"action_digest": row["action_digest"], "subject": row["subject"], "consumed_at": now}
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()
