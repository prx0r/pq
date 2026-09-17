from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ControlSequence:
    digits: tuple[int,...]
    action: str
    description: str
    context_tags: tuple[str,...]=()

class SequenceRegistry:
    def __init__(self):
        self._seq={}

    def register(self,seq:ControlSequence):
        if not seq.digits or any(x not in range(10) for x in seq.digits):
            raise ValueError("sequence digits must be 0..9")
        if seq.digits in self._seq:
            raise ValueError("duplicate sequence")
        self._seq[seq.digits]=seq

    def resolve(self,digits:list[int]|tuple[int,...],tags:set[str]|None=None):
        seq=self._seq.get(tuple(digits))
        if not seq: return None
        if seq.context_tags and not set(seq.context_tags).issubset(tags or set()):
            return None
        return seq

    def list(self):
        return list(self._seq.values())

def default_sequences():
    r=SequenceRegistry()
    r.register(ControlSequence((7,5),"APPROVE_BOUNDED_AND_CONTINUE",
        "Approve the currently proposed bounded grant and resume the parent branch."))
    r.register(ControlSequence((1,3),"REJECT_AND_REPLAN",
        "Reject the current proposal and force a different route."))
    r.register(ControlSequence((4,5),"CHEAPER_AND_CONTINUE",
        "Prefer the cheaper admissible route then continue."))
    r.register(ControlSequence((0,5),"REQUEST_CONTEXT_THEN_CONTINUE",
        "Request the missing context, then continue after it is supplied."))
    return r
