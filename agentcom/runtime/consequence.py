"""One consequence gate for externally visible or irreversible actions."""
from __future__ import annotations

import time
from typing import Callable, Any

from agentcom.authority.grants import AuthorityAction, Grant, GrantStore, GrantVerifier


class ConsequenceGate:
    def __init__(self, verifier: GrantVerifier, store: GrantStore):
        self.verifier = verifier
        self.store = store

    def execute(
        self,
        action: AuthorityAction,
        grant: Grant,
        *,
        effect: Callable[[], Any],
        budget_check: Callable[[AuthorityAction], None] | None = None,
        policy_check: Callable[[AuthorityAction], None] | None = None,
        settle: Callable[[AuthorityAction, Any], Any] | None = None,
    ) -> dict:
        if budget_check:
            budget_check(action)
        if policy_check:
            policy_check(action)
        # Signature/binding is checked before touching the use counter.
        self.verifier.verify(grant, action)
        # Atomic consumption is deliberately the final step before effect.
        use_no = self.store.consume(grant, action, self.verifier)
        started = int(time.time())
        try:
            result = effect()
        except Exception as exc:
            return {
                "ok": False,
                "action_digest": action.digest,
                "grant_id": grant.grant_id,
                "grant_use": use_no,
                "effect_started_at": started,
                "error": f"{type(exc).__name__}: {exc}",
            }
        settlement = settle(action, result) if settle else None
        return {
            "ok": True,
            "action_digest": action.digest,
            "grant_id": grant.grant_id,
            "grant_use": use_no,
            "effect_started_at": started,
            "result": result,
            "settlement": settlement,
        }
