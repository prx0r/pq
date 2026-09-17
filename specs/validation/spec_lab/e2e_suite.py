from __future__ import annotations
import json
from pathlib import Path
from .drivers import RecordedDriver
from .mission_sim import MissionSimulator

ROOT=Path(__file__).resolve().parents[1]
SPEC=(ROOT/"specs/ghostcompute_long_spec.md").read_text()
ORACLE=json.loads((ROOT/"fixtures/oracle_ghostcompute.json").read_text())

def _run():
    return MissionSimulator(RecordedDriver(ORACLE),SPEC).run_tournament(variants=5)

def run_e2e_suite():
    r=_run()
    rows=[]
    def add(i,h,ok,detail):
        rows.append({"id":i,"hypothesis":h,"pass":bool(ok),"detail":detail})

    shadow=r["shadow_lanes"]
    live=r["live_run"]
    add(
        "shadow_no_consequence",
        "Candidate tournaments execute no live consequences",
        all(x["live_effect_count"]==0 for x in shadow),
        f"shadow_live_effects={[x['live_effect_count'] for x in shadow]}",
    )
    cap=float(r["mission"]["budget"]["irreversible_actions"])
    add(
        "live_effect_cap",
        "Promoted live run stays inside irreversible consequence cap",
        r["live_effect_count"]<=cap,
        f"live_effect_count={r['live_effect_count']} cap={cap}",
    )
    add(
        "one_live_lane",
        "Only the promoted policy crosses the live consequence belt",
        live is not None and live["validation_class"]=="LIVE",
        f"live={live['lane']['id'] if live else None}",
    )
    add(
        "human_once",
        "Shared owner-only blocker creates one real human request, not one per lane",
        r["mission_human"]["requests"]==1,
        json.dumps(r["mission_human"]),
    )
    add(
        "human_budget",
        "Human attention stays inside mission cap",
        r["mission_human"]["minutes"]<=float(r["mission"]["budget"]["human_minutes"]),
        f"human={r['mission_human']['minutes']} cap={r['mission']['budget']['human_minutes']}",
    )
    add(
        "all_shadow_valid",
        "All compared lanes are judged under the same replayable world and finish",
        all(x["lane"]["qp_valid"] for x in shadow),
        f"invalid={[x['lane']['id'] for x in shadow if not x['lane']['qp_valid']]}",
    )
    add(
        "live_actuality",
        "Promoted live run reaches the frozen mandatory Actuality root",
        bool(live and live["lane"]["actuality"] and live["lane"]["qp_valid"]),
        f"actuality={live['lane']['actuality'] if live else None}",
    )
    add(
        "reuse_wins",
        "The planted world selects the lower-waste reuse-first policy",
        r["winner_policy"]=="policy.reuse_first",
        f"winner={r['winner_policy']}",
    )
    live_effect_kinds=[x["kind"] for x in live["effects"]]
    add(
        "merge_last",
        "GitHub merge is delayed until all prerequisite proof work is done",
        bool(live_effect_kinds and live_effect_kinds[-1]=="github.pr.merge"),
        f"effects={live_effect_kinds}",
    )
    routes={x["covers"][0]:x["route_id"] for x in r["base_plan"]}
    add(
        "no_new_wallet",
        "Plan reuses the existing XMR primitive instead of building a wallet path",
        routes.get("leaf.xmr_settlement")=="reuse-xmr-payment-module",
        f"route={routes.get('leaf.xmr_settlement')}",
    )
    add(
        "no_optional_ui",
        "Optional Web UI does not appear as an A-Task",
        not any("ui" in x["objective"].lower() for x in r["base_plan"]),
        "checked base-plan objectives",
    )
    model_total=sum(float(x["lane"]["metrics"]["cost_usd"]) for x in shadow)+float(live["lane"]["metrics"]["cost_usd"])
    add(
        "model_budget",
        "Tournament plus live run stays inside total model/API budget",
        model_total<=float(r["mission"]["budget"]["model_api_usd"]),
        f"sim_model_cost={model_total:.6f} cap={r['mission']['budget']['model_api_usd']}",
    )
    add(
        "variant_cap",
        "Variant count respects specification cap",
        len(shadow)<=int(r["mission"]["budget"]["variants"]),
        f"variants={len(shadow)} cap={r['mission']['budget']['variants']}",
    )

    return {
        "passed":sum(x["pass"] for x in rows),
        "failed":sum(not x["pass"] for x in rows),
        "total":len(rows),
        "rows":rows,
        "run":r,
    }
