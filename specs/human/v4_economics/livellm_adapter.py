from __future__ import annotations
from typing import Any
from .router import ModelOffer

def offers_from_livellm(payload: dict[str,Any]) -> list[ModelOffer]:
    """Best-effort adapter for LiveLLM-style canonical market payloads.

    The exact LiveLLM JSON can evolve; this adapter only accepts facts that expose
    explicit model/provider/pricing fields. Missing monetary values are skipped
    rather than guessed as zero.
    """
    rows=payload.get("models") or payload.get("routes") or payload.get("data") or []
    out=[]
    for row in rows:
        pricing=row.get("pricing") or row.get("economics") or row
        ip=pricing.get("input_per_million")
        op=pricing.get("output_per_million")
        if ip is None or op is None:
            continue
        out.append(ModelOffer(
            model_id=str(row.get("model_id") or row.get("model") or row.get("id")),
            provider=str(row.get("provider") or row.get("route") or "unknown"),
            input_per_million=float(ip),
            output_per_million=float(op),
            cached_input_per_million=(
                float(pricing["cached_input_per_million"])
                if pricing.get("cached_input_per_million") is not None else None
            ),
            context_tokens=row.get("context_tokens") or row.get("context_window"),
            latency_ms=row.get("latency_ms"),
            free_tier=bool(row.get("free_tier",False)),
            evidence_ids=tuple(row.get("evidence_ids") or []),
            observed_at=row.get("observed_at"),
        ))
    return out
