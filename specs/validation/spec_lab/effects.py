from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .canonical import digest
from .policies import KernelPolicy, FINAL_POLICY

class InjectedCrash(RuntimeError):
    pass

@dataclass
class EffectJournal:
    prepared: dict[str, dict[str, Any]] = field(default_factory=dict)
    committed: dict[str, dict[str, Any]] = field(default_factory=dict)
    physical_effect_count: int = 0

    def execute(
        self,
        *,
        action: dict[str, Any],
        idempotency_key: str,
        crash_at: str | None = None,
        policy: KernelPolicy = FINAL_POLICY,
    ) -> dict[str, Any]:
        if policy.idempotent_effects and idempotency_key in self.committed:
            return dict(self.committed[idempotency_key])

        prepared={"id":digest("prepared-effect",{"action":action,"key":idempotency_key}),"action":action}
        self.prepared[idempotency_key]=prepared
        if crash_at=="after_prepare":
            raise InjectedCrash("after_prepare")

        consequence={
            "effect_id":digest("external-effect",{"action":action,"key":idempotency_key,"n":self.physical_effect_count+1}),
            "status":"COMMITTED",
            "idempotency_key":idempotency_key,
        }
        self.physical_effect_count += 1
        self.committed[idempotency_key]=consequence
        if crash_at=="after_commit":
            raise InjectedCrash("after_commit")
        return dict(consequence)
