from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass(frozen=True)
class QueryOutcomeEvent:
    query_id: str
    timestamp: str
    actor_type: str
    query: str
    graph_state_refs: List[str]
    recommendation_ref: Optional[str]
    action_ref: Optional[str]
    outcome: str
    outcome_value: Optional[float]
    consent_scope: str
    provenance_refs: List[str]

    def to_dict(self):
        return asdict(self)
