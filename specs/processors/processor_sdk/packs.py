from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RuntimePack:
    id: str
    trigger: str
    sequence: tuple[str, ...]
    stop_when: str
    max_depth: int = 8

class RuntimePackRegistry:
    def __init__(self):
        self._packs={}

    def register(self, pack: RuntimePack):
        if pack.id in self._packs:
            raise ValueError(f"duplicate runtime pack {pack.id}")
        self._packs[pack.id]=pack

    def get(self, pack_id: str) -> RuntimePack:
        return self._packs[pack_id]

    def list(self):
        return list(self._packs.values())

def default_runtime_packs() -> RuntimePackRegistry:
    r=RuntimePackRegistry()
    r.register(RuntimePack(
        "proof.stuck",
        "proof obligation remains UNKNOWN after bounded direct attempt",
        (
            "history.retrieve",
            "reuse.search",
            "tool.discover",
            "web.search",
            "data.discover",
            "problem.decompose",
            "cg.simulate",
            "redteam.falsify",
            "repair.propose",
        ),
        "a new admissible evidence route exists OR blocker is certified",
    ))
    r.register(RuntimePack(
        "implementation.failing",
        "build/test processor failed twice",
        (
            "failure.classify",
            "history.retrieve",
            "redteam.falsify",
            "repair.propose",
            "replace.component",
            "cg.compare",
        ),
        "one candidate passes the same frozen evaluator",
    ))
    r.register(RuntimePack(
        "uncertainty.high",
        "claim remains UNKNOWN and information value is high",
        (
            "history.retrieve",
            "web.search",
            "data.discover",
            "tool.discover",
            "probe.design",
            "cg.simulate",
        ),
        "evidence route can settle or falsify the claim",
    ))
    r.register(RuntimePack(
        "post.success.optimize",
        "mandatory Actuality TRUE and trajectory verified",
        (
            "trajectory.analyse",
            "seed0.mutate",
            "cg.replay",
            "cg.compare",
            "policy.promote.propose",
        ),
        "candidate beats control under frozen hard gates",
    ))
    return r
