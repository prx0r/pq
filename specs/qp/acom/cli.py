"""A-COM node CLI. Thin shell over kernel + killfeed; adds no semantics.

  python3 -m acom.cli init <dir>          fresh store
  python3 -m acom.cli demo                HBM claim + generic task
  python3 -m acom.cli verify <receipt> <evidence>
  python3 -m acom.cli chain <store>
  python3 -m acom.cli evidence add <store> <evidence.json>
  python3 -m acom.cli claim <world> <PRED> <date>
  python3 -m acom.cli world replay <world>
  python3 -m acom.cli state root <world>
  python3 -m acom.cli killfeed [--world <id>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acom import store as store_mod  # noqa: E402
from acom.receipts import settle, verify_receipt  # noqa: E402


def main() -> int:
    """Node entrypoint. Machine-readable JSON on stdout; exit code
    mirrors the verdict so automation never parses text."""
    ap = argparse.ArgumentParser(prog="acom")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("dir")
    sub.add_parser("demo")
    p = sub.add_parser("verify")
    p.add_argument("receipt"); p.add_argument("evidence")
    p = sub.add_parser("chain"); p.add_argument("store")
    p = sub.add_parser("evidence"); p.add_argument("add", nargs="?",
                                                   default="add")
    p.add_argument("store"); p.add_argument("file")
    p = sub.add_parser("claim"); p.add_argument("world"); p.add_argument("pred")
    p.add_argument("date")
    p = sub.add_parser("world"); p.add_argument("replay", nargs="?",
                                                default="replay")
    p.add_argument("world")
    p = sub.add_parser("state"); p.add_argument("root", nargs="?",
                                                default="root")
    p.add_argument("world")
    p = sub.add_parser("killfeed"); p.add_argument("--world", default="")
    a = ap.parse_args()

    if a.cmd == "init":
        os.makedirs(a.dir, exist_ok=True)
        open(os.path.join(a.dir, "events.jsonl"), "a").close()
        print(json.dumps({"ok": True, "store": a.dir + "/events.jsonl"}))
        return 0
    if a.cmd == "demo":
        from examples import hbm_demo, atask_demo
        r1 = hbm_demo.run()
        r2 = atask_demo.run()
        print(json.dumps({"ok": True,
                          "hbm": {"id": r1["id"], "passed": r1["passed"]},
                          "atask": {"id": r2["id"], "passed": r2["passed"]}}))
        return 0 if (r1["passed"] and r2["passed"]) else 1
    if a.cmd == "verify":
        rec = json.load(open(a.receipt))
        ev = json.load(open(a.evidence))
        out = settle(rec, ev)
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    if a.cmd == "chain":
        ok = store_mod.Store(a.store).verify_chain()
        print(json.dumps({"ok": ok}))
        return 0 if ok else 1
    return _killfeed_cmd(a)


def _world(wid):
    import glob
    import yaml
    from killfeed import engine as _e
    d = os.path.join("killfeed", "worlds", wid)
    cfg = yaml.safe_load(open(os.path.join(d, "world.yaml")))
    tl = [json.load(open(f)) for f in sorted(glob.glob(
        os.path.join(d, "timeline", "*.json")))]
    return {"world_id": cfg["world_id"], "config": cfg, "timeline": tl}


def _killfeed_cmd(a):
    if a.cmd == "evidence":
        st = store_mod.Store(a.store)
        e = json.load(open(a.file))
        out = st.append("evidence", e)
        print(json.dumps({"ok": True, "hash": out["hash"],
                          "cursor": st.cursor}))
        return 0
    if a.cmd == "claim":
        from killfeed import circuit as _c
        from killfeed import engine as _e
        w = _world(a.world)
        snap = next(s for s in w["timeline"] if s["date"] == a.date)
        from killfeed import engine as _e
        usable, _, _ = _e.admissible(
            snap["evidence"], a.date, w["config"].get("max_age_days", 400))
        node = w["config"]["predicates"][a.pred]["circuit"]
        params = _e.predicate_params(w["config"]["predicates"][a.pred])
        v, m = _c.evaluate_margin(node, usable, a.date, params=params)
        print(json.dumps({"predicate": a.pred, "verdict": v,
                          "margin": m}))
        return 0
    if a.cmd == "world":
        from killfeed import engine as _e
        for r in _e.evaluate_world(_world(a.world)):
            print(f"{r['as_of']} {r['state_after']} {r['claim_states']}")
        return 0
    if a.cmd == "state":
        from killfeed import engine as _e
        rs = _e.evaluate_world(_world(a.world))
        print(json.dumps({"world": a.world,
                          "state_root": _e.world_state_root(rs)}))
        return 0
    if a.cmd == "killfeed":
        from killfeed import engine as _e
        import os as _os
        wids = [a.world] if a.world else sorted(_os.listdir(
            os.path.join("killfeed", "worlds")))
        for wid in wids:
            for k in _e.kill_events(_world(wid)):
                print(f"{k['date']} {k['world']} {k['predicate']} "
                      f"{k['from']}->{k['to']} trade={k['trade']}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
