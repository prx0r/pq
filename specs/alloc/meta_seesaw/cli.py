from __future__ import annotations
import argparse, json
from pathlib import Path
from .models import Project, CostVector
from .scorer import rank_portfolio


def load(path: Path):
    raw = json.loads(path.read_text())
    projects = []
    for p in raw['projects']:
        c = CostVector(**p.pop('costs', {}))
        projects.append(Project(costs=c, **p))
    return raw.get('portfolio_id', path.stem), projects, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('portfolio_json')
    ap.add_argument('--slots', type=int, default=2)
    args = ap.parse_args()
    pid, projects, raw = load(Path(args.portfolio_json))
    decision = rank_portfolio(pid, projects, scarce_asset_slots=args.slots,
                              infra_attention_cap=raw.get('infra_attention_cap', 0.30))
    print(json.dumps(decision.to_dict(), indent=2))

if __name__ == '__main__':
    main()
