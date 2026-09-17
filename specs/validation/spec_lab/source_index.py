from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any

@dataclass(frozen=True)
class Section:
    ref: str
    number: str
    title: str
    kind: str
    body: str

def _kind(title: str) -> str:
    t=title.lower()
    if "optional" in t or "nice to have" in t or "later" in t:
        return "optional"
    if "non-goal" in t or "out of scope" in t:
        return "non_goal"
    if "budget" in t or "limit" in t:
        return "budget"
    return "normal"

def index_markdown(text: str) -> dict[str, Section]:
    lines=text.splitlines()
    starts=[]
    pat=re.compile(r"^#{1,6}\s+(?:(\d+)\.\s*)?(.*\S)\s*$")
    for i,line in enumerate(lines):
        m=pat.match(line)
        if m and m.group(1):
            starts.append((i,m.group(1),m.group(2).strip()))
    out={}
    for j,(idx,num,title) in enumerate(starts):
        end=starts[j+1][0] if j+1<len(starts) else len(lines)
        body="\n".join(lines[idx+1:end]).strip()
        sec=Section(ref=f"§{num}",number=num,title=title,kind=_kind(title),body=body)
        out[sec.ref]=sec
    return out

def validate_refs(refs: list[str], index: dict[str,Section]) -> tuple[bool,str]:
    for ref in refs:
        if ref.startswith("§") and ref not in index:
            return False,f"unknown source ref {ref}"
    return True,"ok"

def classify_refs(refs: list[str], index: dict[str,Section]) -> set[str]:
    return {index[r].kind for r in refs if r in index}

def extract_hard_caps(text: str) -> dict[str,float]:
    caps={}
    patterns=[
        ("usd", r"external spend[^\n]{0,80}?(?:USD|\$)\s*([0-9]+(?:\.[0-9]+)?)"),
        ("model_api_usd", r"(?:model/API inference cost|model api inference cost)[^\n]{0,80}?(?:USD|\$)\s*([0-9]+(?:\.[0-9]+)?)"),
        ("human_minutes", r"human attention[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)\s*minutes"),
        ("irreversible_actions", r"irreversible external consequences[^\n]{0,80}?(?:at most|maximum|max)\s*([0-9]+)"),
        ("variants", r"variants[^\n]{0,80}?(?:up to|at most|maximum|max)\s*([0-9]+)"),
    ]
    for key,pat in patterns:
        m=re.search(pat,text,re.I)
        if m:
            caps[key]=float(m.group(1))
    return caps
