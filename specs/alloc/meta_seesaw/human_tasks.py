from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, List, Dict

HUMAN_BOUNDARIES = {
    'authority', 'money', 'secret', 'physical', 'preference', 'legal', 'ood_judgment'
}

@dataclass(frozen=True)
class HumanTask:
    id: str
    boundary: str
    question: str
    actions_0_9: Dict[str, str]
    blocking: bool
    created_at_compile: bool = True

    def to_dict(self):
        return asdict(self)


def compile_human_tasks(task_specs: Iterable[dict]) -> List[HumanTask]:
    out = []
    for i, spec in enumerate(task_specs):
        boundary = spec.get('human_boundary')
        if boundary not in HUMAN_BOUNDARIES:
            continue
        actions = spec.get('actions_0_9') or {'0': 'reject', '1': 'approve'}
        if len(actions) > 10:
            raise ValueError('H-task control surface supports at most 10 semantic actions')
        out.append(HumanTask(
            id=spec.get('id', f'h{i}'),
            boundary=boundary,
            question=spec.get('question', 'Human decision required'),
            actions_0_9={str(k): str(v) for k, v in actions.items()},
            blocking=bool(spec.get('blocking', True)),
        ))
    return out
