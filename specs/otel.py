"""OTel GenAI mapping (outward only): canonical telemetry -> provider-neutral
span dicts in OpenTelemetry GenAI vocabulary. No otel dependency; plain
dicts a real exporter can forward. Our schema stays canonical — this is a
projection for Braintrust/Grafana-style backends, never the truth store.
"""
GENAI = {"system": "gen_ai.system", "request.model": "gen_ai.request.model",
         "usage.input": "gen_ai.usage.input_tokens",
         "usage.output": "gen_ai.usage.output_tokens",
         "response.id": "gen_ai.response.id"}


def to_spans(records, system="agentcom"):
    """Telemetry records -> OTel-style spans [{name, kind, attributes,
    status}]. Pure; unknowns stay null."""
    out = []
    for r in records or []:
        r = r if isinstance(r, dict) else {}
        cost = r.get("cost", {}) or {}
        out.append({
            "name": str(r.get("attempt_id") or r.get("name", "attempt")),
            "kind": "CLIENT",
            "attributes": {
                GENAI["system"]: system,
                GENAI["request.model"]: r.get("model"),
                GENAI["usage.input"]: cost.get("tokens"),
                GENAI["response.id"]: r.get("run_id"),
                "agentcom.verdict": (r.get("observed_effect") or {})
                .get("verdict", "UNKNOWN"),
            },
            "status": {"code": "OK" if (r.get("observed_effect") or {})
                       .get("verdict") == "PASS" else "UNSET"},
        })
    return out
