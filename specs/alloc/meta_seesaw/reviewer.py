from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Literal

@dataclass(frozen=True)
class ProofObligation:
    id: str
    claim: str
    evidence_needed: str
    verifier: str

@dataclass(frozen=True)
class ReviewRequest:
    mission_id: str
    actuality_target: str
    failed_obligations: List[str]
    evidence_refs: List[str]
    remaining_time_minutes: int
    remaining_budget: float

@dataclass(frozen=True)
class ReviewResponse:
    status: Literal['PROPOSED']
    critique: List[str]
    proof_ladder: List[ProofObligation]
    authority_granted: Literal[False] = False
    truth_settled: Literal[False] = False

    def to_dict(self):
        return asdict(self)


def make_recovery_ladder(req: ReviewRequest) -> ReviewResponse:
    # Deterministic skeleton for a lead-model/ChatGPT reviewer. The actual lead model
    # may fill these steps, but cannot certify completion or grant authority.
    ladder = [
        ProofObligation('p0', 'Clarify the exact failed claim', 'smallest reproducible failure state', 'independent probe'),
        ProofObligation('p1', 'Establish observable preconditions', 'fresh state/provenance snapshot', 'deterministic validator'),
        ProofObligation('p2', 'Attempt the minimum corrective action', 'execution receipt / diff / transaction result', 'effect probe'),
        ProofObligation('p3', 'Verify desired external reality', req.actuality_target, 'Actuality judge'),
        ProofObligation('p4', 'Check regression / replay', 'repeat or adversarial re-check', 'QP-compatible validator'),
    ]
    critique = []
    if not req.evidence_refs:
        critique.append('No evidence refs supplied; recover observation before more action.')
    if req.remaining_time_minutes <= 15:
        critique.append('Time budget is nearly exhausted; prefer probe/rollback/escalation over broad exploration.')
    if req.remaining_budget <= 0:
        critique.append('Money budget exhausted; no paid effect should be proposed.')
    for f in req.failed_obligations:
        critique.append(f'Recover typed failure: {f}')
    return ReviewResponse(status='PROPOSED', critique=critique, proof_ladder=ladder)
