import argparse, json
from pathlib import Path
from .engine import score_portfolio, get_project, score_features, event_impact
from .scoring import project_score
from .report import portfolio_markdown

def load(path):
    return json.loads(Path(path).read_text())

def print_table(rows, cols):
    widths={c:max(len(str(c)), max([len(str(r.get(c,""))) for r in rows] or [0])) for c in cols}
    print(" | ".join(str(c).ljust(widths[c]) for c in cols))
    print("-+-".join("-"*widths[c] for c in cols))
    for r in rows:
        print(" | ".join(str(r.get(c,"")).ljust(widths[c]) for c in cols))

def main():
    ap=argparse.ArgumentParser(prog="seesaw")
    sub=ap.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("portfolio")
    p.add_argument("portfolio")

    one=sub.add_parser("project")
    one.add_argument("portfolio")
    one.add_argument("--id",required=True)

    f=sub.add_parser("features")
    f.add_argument("portfolio")
    f.add_argument("--id",required=True)

    e=sub.add_parser("event")
    e.add_argument("event")
    e.add_argument("portfolio")

    r=sub.add_parser("report")
    r.add_argument("portfolio")
    r.add_argument("--out",required=True)

    a=ap.parse_args()

    if a.cmd=="portfolio":
        rows=score_portfolio(load(a.portfolio))
        print_table(rows,["id","strategic_value","moat","fragility","ownership","action"])

    elif a.cmd=="project":
        portfolio=load(a.portfolio)
        project=get_project(portfolio,a.id)
        print(json.dumps(project_score(project),indent=2))

    elif a.cmd=="features":
        portfolio=load(a.portfolio)
        project=get_project(portfolio,a.id)
        print_table(score_features(project),["name","score","action"])

    elif a.cmd=="event":
        ev=load(a.event)
        pf=load(a.portfolio)
        print_table(event_impact(pf,ev),["id","before","after","delta","new_action"])

    elif a.cmd=="report":
        pf=load(a.portfolio)
        out=Path(a.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(portfolio_markdown(pf))
        print(out)

if __name__=="__main__":
    main()
