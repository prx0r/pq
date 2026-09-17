from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Literal

Kind = Literal['asset', 'data_asset', 'infra', 'explore']

@dataclass(frozen=True)
class CostVector:
    human: float = 0.0
    cash: float = 0.0
    risk: float = 0.0
    verification: float = 0.0

@dataclass(frozen=True)
class Project:
    id: str
    kind: Kind
    capital: float
    urgency: float
    unlock: float
    moat: float
    reuse: float
    information_gain: float
    first_mover: float
    proximity: float
    strategic_fit: float
    costs: CostVector = field(default_factory=CostVector)
    deadline_days: Optional[int] = None
    opportunity_window_days: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    notes: str = ''

@dataclass(frozen=True)
class ScoreBreakdown:
    project_id: str
    benefit: float
    cost_penalty: float
    deadline_boost: float
    window_boost: float
    dependency_unlock: float
    priority: float
    lane: str
    action: str
    reasons: List[str]

@dataclass(frozen=True)
class StrategicDecision:
    status: Literal['PROPOSED']
    portfolio_id: str
    ranking: List[str]
    scores: Dict[str, ScoreBreakdown]
    asset_slots: List[str]
    infra_support: List[str]
    watch: List[str]
    constraints: Dict[str, object]

    def to_dict(self):
        out = asdict(self)
        return out
