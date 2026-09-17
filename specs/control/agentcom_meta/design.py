from __future__ import annotations
from dataclasses import dataclass
from .experiment import LaneSpec,DEFAULT_LANES
from .memory import RunBank

@dataclass(frozen=True)
class DesignedLane:
    lane:LaneSpec
    parent_run_id:str|None
    inherited_processors:tuple[str,...]
    must_mutate:bool
    mutation_reason:str


def design_five_from_history(runbank:RunBank,features:tuple[str,...]):
    """Exploit a verified foundation without collapsing the tournament.

    Two lanes may inherit the best known foundation. Three lanes are forced to mutate
    mechanism/search/world assumptions. No historical run is authoritative; it is a prior.
    """
    f=runbank.foundation(features)
    out=[]
    for i,l in enumerate(DEFAULT_LANES):
        inherit=f.processor_ids if f and i<2 else ()
        out.append(DesignedLane(l,f.run_id if f else None,inherit,i>=2,
            l.mutation if i>=2 else ('reuse-foundation' if f else 'cold-start')))
    return tuple(out)
