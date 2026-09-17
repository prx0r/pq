"""Adapter contract for prx0r/agentcomfinal.

This module deliberately emits proposals only. It is designed to sit beside the
canonical autobuild/compiler/seesaw.py and feed AgentCom's portfolio scheduler.
QP remains the only truth/authority settlement boundary.
"""
from .scorer import rank_portfolio


def propose_portfolio(portfolio_id, projects, scarce_asset_slots=2, infra_attention_cap=0.30):
    return rank_portfolio(
        portfolio_id,
        projects,
        scarce_asset_slots=scarce_asset_slots,
        infra_attention_cap=infra_attention_cap,
    ).to_dict()
