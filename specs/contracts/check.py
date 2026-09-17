"""Contracts enforcement: the 5 schemas are law, not decoration.

Minimal JSON-schema-subset validator (object/array/string/integer/number/
boolean, required, properties, items, enum, minItems/maxItems, minimum/
maximum). check(kind, obj) loads contracts/<kind>.schema.json. Real objects
(lineage chains, trajectories, proposals) are validated in tests — a schema
nothing checks is a wish.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _check(obj, schema, path, reasons):
    t = schema.get("type")
    if t == "object":
        if not isinstance(obj, dict):
            reasons.append("%s: want object" % path)
            return
        for k in schema.get("required", []):
            if k not in obj:
                reasons.append("%s: missing %s" % (path, k))
        for k, sub in schema.get("properties", {}).items():
            if k in obj and isinstance(sub, dict):
                _check(obj[k], sub, "%s.%s" % (path, k), reasons)
    elif t == "array":
        if not isinstance(obj, list):
            reasons.append("%s: want array" % path)
            return
        n = len(obj)
        if "minItems" in schema and n < schema["minItems"]:
            reasons.append("%s: minItems" % path)
        if "maxItems" in schema and n > schema["maxItems"]:
            reasons.append("%s: maxItems" % path)
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(obj):
                _check(item, schema["items"], "%s[%d]" % (path, i), reasons)
    elif t == "string":
        if not isinstance(obj, str):
            reasons.append("%s: want string" % path)
    elif t == "integer":
        if not isinstance(obj, int) or isinstance(obj, bool):
            reasons.append("%s: want integer" % path)
    elif t == "number":
        if not isinstance(obj, (int, float)) or isinstance(obj, bool):
            reasons.append("%s: want number" % path)
    elif t == "boolean":
        if not isinstance(obj, bool):
            reasons.append("%s: want boolean" % path)
    if "enum" in schema and obj not in schema["enum"]:
        reasons.append("%s: not in enum" % path)
    if "minimum" in schema and isinstance(obj, (int, float)) \
            and obj < schema["minimum"]:
        reasons.append("%s: below minimum" % path)
    if "maximum" in schema and isinstance(obj, (int, float)) \
            and obj > schema["maximum"]:
        reasons.append("%s: above maximum" % path)


def check(kind, obj):
    """kind: strategic|campaign|actuality|trajectory|promotion.
    Returns (ok, reasons). Never raises on bad input."""
    try:
        with open(os.path.join(ROOT, kind + ".schema.json"),
                  encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, ValueError):
        return False, ["schema-missing:%s" % kind]
    reasons = []
    try:
        _check(obj, schema, "$", reasons)
    except Exception:  # noqa: BLE001 - checker never raises
        return False, reasons + ["checker-error"]
    return (not reasons), reasons
