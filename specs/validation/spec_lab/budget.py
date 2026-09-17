from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

FIELDS = ("usd", "input_tokens", "output_tokens", "wall_seconds", "human_minutes", "irreversible_actions")

@dataclass
class BudgetLedger:
    limit: dict[str, float | int | None]
    used: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in FIELDS})

    def remaining(self, key: str) -> float | None:
        cap = self.limit.get(key)
        if cap is None:
            return None
        return float(cap) - self.used.get(key, 0.0)

    def can(self, delta: dict[str, Any]) -> tuple[bool, str]:
        for key in FIELDS:
            if key not in delta:
                continue
            value = delta.get(key)
            cap = self.limit.get(key)
            if value is None:
                if cap is not None:
                    return False, f"budget:{key}:unknown"
                continue
            if cap is None:
                continue
            if self.used.get(key, 0.0) + float(value) > float(cap):
                return False, f"budget:{key}"
        return True, "ok"

    def record(self, delta: dict[str, Any]) -> tuple[bool, str]:
        ok, reason = self.can(delta)
        if not ok:
            return False, reason
        for key in FIELDS:
            if delta.get(key) is not None:
                self.used[key] = self.used.get(key, 0.0) + float(delta[key])
        return True, "recorded"

    def pressure(self) -> str:
        ratios = []
        for key in FIELDS:
            cap = self.limit.get(key)
            if cap is None or float(cap) <= 0:
                continue
            ratios.append(self.used.get(key, 0.0) / float(cap))
        x = max(ratios, default=0)
        if x < 0.60:
            return "GREEN"
        if x < 0.80:
            return "AMBER"
        if x < 1.0:
            return "RED"
        return "STOP"
