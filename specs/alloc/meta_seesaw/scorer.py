from __future__ import annotations
import math
from typing import Dict, Iterable, List
from .models import Project, ScoreBreakdown, StrategicDecision

BENEFIT_WEIGHTS = {
    'capital': 2.20,
    'urgency': 1.80,
    'unlock': 1.85,
    'moat': 1.55,
    'reuse': 1.25,
    'information_gain': 1.10,
    'first_mover': 1.20,
    'proximity': 0.90,
    'strategic_fit': 1.10,
}
COST_WEIGHTS = {'human': 1.30, 'cash': 0.70, 'risk': 1.00, 'verification': 0.85}


def _bounded(v: float) -> float:
    return max(0.0, min(5.0, float(v)))


def _deadline_boost(days):
    if days is None:
        return 1.0
    d = max(0, int(days))
    # Smoothly rewards expiring windows without letting urgency dominate forever.
    return 1.0 + 0.85 * math.exp(-d / 28.0)


def _window_boost(days):
    if days is None:
        return 1.0
    d = max(0, int(days))
    return 1.0 + 0.55 * math.exp(-d / 21.0)


def _dependency_unlock(project: Project, projects: Dict[str, Project]) -> float:
    # A small, capped bonus for projects that are prerequisites of valuable downstream work.
    downstream = [p for p in projects.values() if project.id in p.dependencies]
    if not downstream:
        return 0.0
    raw = sum((_bounded(p.capital) + _bounded(p.strategic_fit) + _bounded(p.moat)) / 15.0 for p in downstream)
    return min(2.0, raw)


def score_project(project: Project, projects: Dict[str, Project]) -> ScoreBreakdown:
    benefit = sum(BENEFIT_WEIGHTS[k] * _bounded(getattr(project, k)) for k in BENEFIT_WEIGHTS)
    costs = project.costs
    weighted_cost = sum(COST_WEIGHTS[k] * _bounded(getattr(costs, k)) for k in COST_WEIGHTS)
    cost_penalty = 1.0 + weighted_cost / 16.0
    deadline = _deadline_boost(project.deadline_days)
    window = _window_boost(project.opportunity_window_days)
    dep = _dependency_unlock(project, projects)
    priority = ((benefit + 2.0 * dep) * deadline * window) / cost_penalty

    reasons: List[str] = []
    if project.deadline_days is not None and project.deadline_days <= 45:
        reasons.append('expiring deadline')
    if project.opportunity_window_days is not None and project.opportunity_window_days <= 21:
        reasons.append('first-mover window')
    if project.unlock >= 4:
        reasons.append('removes cross-project bottlenecks')
    if project.moat >= 4:
        reasons.append('builds scarce/compounding asset')
    if project.capital >= 4:
        reasons.append('near-term capital potential')
    if project.reuse >= 4:
        reasons.append('high reuse')

    if project.kind == 'infra':
        lane = 'SUPPORT'
        action = 'BUILD_AS_NEEDED'
    elif priority >= 42:
        lane, action = 'NOW', 'EXECUTE'
    elif priority >= 32:
        lane, action = 'NEXT', 'VALIDATE_OR_BUILD'
    elif priority >= 24:
        lane, action = 'LATER', 'WATCH_OR_PROBE'
    else:
        lane, action = 'PARK', 'DROP_OR_DEFER'

    return ScoreBreakdown(
        project_id=project.id,
        benefit=round(benefit, 3),
        cost_penalty=round(cost_penalty, 3),
        deadline_boost=round(deadline, 3),
        window_boost=round(window, 3),
        dependency_unlock=round(dep, 3),
        priority=round(priority, 3),
        lane=lane,
        action=action,
        reasons=reasons,
    )


def rank_portfolio(portfolio_id: str, projects: Iterable[Project], scarce_asset_slots: int = 2,
                   infra_attention_cap: float = 0.30) -> StrategicDecision:
    plist = list(projects)
    by_id = {p.id: p for p in plist}
    scored = {p.id: score_project(p, by_id) for p in plist}
    ranking = sorted(scored, key=lambda x: scored[x].priority, reverse=True)

    assets = [pid for pid in ranking if by_id[pid].kind in ('asset', 'data_asset')]
    infra = [pid for pid in ranking if by_id[pid].kind == 'infra']
    watch = [pid for pid in ranking if by_id[pid].kind == 'explore' or scored[pid].lane in ('LATER', 'PARK')]

    return StrategicDecision(
        status='PROPOSED',
        portfolio_id=portfolio_id,
        ranking=ranking,
        scores=scored,
        asset_slots=assets[:max(0, scarce_asset_slots)],
        infra_support=infra,
        watch=watch,
        constraints={
            'infra_attention_cap': infra_attention_cap,
            'infra_cannot_take_scarce_external_asset_slot': True,
            'seesaw_may_propose_but_not_settle_truth_or_authority': True,
        },
    )
