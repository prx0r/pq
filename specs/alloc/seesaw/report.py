from .engine import score_portfolio, score_features, get_project

def portfolio_markdown(portfolio):
    rows=score_portfolio(portfolio)
    lines=["# Seesaw Portfolio Report","",
           "| Project | Strategic value | Moat | Fragility | Ownership | Action |",
           "|---|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['name']} | {r['strategic_value']} | {r['moat']} | {r['fragility']} | {r['ownership']} | {r['action']} |")
    lines += ["","## Feature priorities",""]
    for r in rows:
        p=get_project(portfolio,r["id"])
        lines += [f"### {p['name']}","",
                  "| Feature | Score | Action |","|---|---:|---|"]
        for f in score_features(p):
            lines.append(f"| {f['name']} | {f['score']} | {f['action']} |")
        lines.append("")
    return "\n".join(lines)
