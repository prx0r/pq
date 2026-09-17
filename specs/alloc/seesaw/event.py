def describe_event(event):
    lines=[f"# {event.get('name')}", "", event.get("description",""), "", "## Deltas", ""]
    for k,v in sorted(event.get("deltas",{}).items()):
        sign="+" if v>=0 else ""
        lines.append(f"- `{k}`: {sign}{v}")
    if event.get("notes"):
        lines += ["","## Notes",""] + [f"- {n}" for n in event["notes"]]
    return "\n".join(lines)
