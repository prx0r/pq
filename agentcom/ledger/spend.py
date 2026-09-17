"""Spend ledger — real usage totals behind the status feed.

Every lane run records evidence events + wall time; the bridge reads totals
for per-tile burn display. Integer minor units for money, matching the
QuotaLedger convention. No wallet keys live here.
"""
from __future__ import annotations

import json
import os
import time


class SpendLedger:
    def __init__(self, log_path: str = ""):
        self.entries: list[dict] = []
        self.log_path = log_path
        if log_path and os.path.exists(log_path):
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self.entries.append(json.loads(line))
                        except ValueError:
                            continue

    def record(self, campaign: str, lane: str, evidence_events: int,
               wall_ms: int, usd_minor: int = 0) -> dict:
        e = {"campaign": campaign, "lane": lane,
             "evidence_events": evidence_events, "wall_ms": wall_ms,
             "usd_minor": usd_minor, "ts": int(time.time())}
        self.entries.append(e)
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(e) + "\n")
        return e

    def totals(self, campaign: str = "") -> dict:
        rows = [e for e in self.entries
                if not campaign or e["campaign"] == campaign]
        return {"campaign": campaign or "all",
                "runs": len(rows),
                "evidence_events": sum(e["evidence_events"] for e in rows),
                "wall_ms": sum(e["wall_ms"] for e in rows),
                "usd_minor": sum(e["usd_minor"] for e in rows)}

    def spent_minor(self, campaign: str = "") -> int:
        return sum(e.get("usd_minor", 0) for e in self.entries
                   if not campaign or e["campaign"] == campaign)

    def check_cap(self, cap_minor: int, campaign: str = "") -> dict:
        """Spend gate. spent >= cap refuses — the caller must stop work."""
        spent = self.spent_minor(campaign)
        ok = spent < cap_minor
        return {"ok": ok, "spent_minor": spent, "cap_minor": cap_minor,
                "remaining_minor": max(cap_minor - spent, 0),
                "campaign": campaign or "all"}


def load_caps(path: str, default: int = 0) -> dict:
    """Caps file: {"demo": 500, "default": 500}. Missing file → default."""
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except ValueError:
            pass
    return {"default": default}


def cap_for(caps: dict, campaign: str, default: int = 0) -> int:
    return int(caps.get(campaign, caps.get("default", default)))
