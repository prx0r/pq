from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List

@dataclass(frozen=True)
class ProofState:
    id: str
    weight: float
    state: str  # PENDING|RUNNING|TRUE|FALSE|UNKNOWN|BLOCKED

@dataclass(frozen=True)
class BudgetState:
    time_budget_min: float
    time_spent_min: float
    cash_budget: float
    cash_spent: float
    human_budget_min: float
    human_spent_min: float


def snapshot(mission_id: str, proofs: List[ProofState], budget: BudgetState, blockers=None, h_tasks=None):
    blockers = blockers or []
    h_tasks = h_tasks or []
    total = sum(max(0.0, p.weight) for p in proofs) or 1.0
    done = sum(max(0.0, p.weight) for p in proofs if p.state == 'TRUE')
    running = next((p.id for p in proofs if p.state == 'RUNNING'), None)
    return {
        'mission_id': mission_id,
        'progress': round(done / total, 4),
        'current_proof': running,
        'proofs': [asdict(p) for p in proofs],
        'blockers': blockers,
        'h_task_queue': h_tasks,
        'budget': {
            **asdict(budget),
            'time_remaining_min': max(0.0, budget.time_budget_min - budget.time_spent_min),
            'cash_remaining': max(0.0, budget.cash_budget - budget.cash_spent),
            'human_remaining_min': max(0.0, budget.human_budget_min - budget.human_spent_min),
        },
        'supervision_mode': 'EXCEPTION_ONLY',
    }
