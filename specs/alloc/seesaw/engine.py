from copy import deepcopy
from .scoring import project_score, feature_score, clamp

def get_project(portfolio, project_id):
    for p in portfolio.get("projects",[]):
        if p.get("id") == project_id:
            return p
    raise KeyError(project_id)

def score_portfolio(portfolio):
    rows=[]
    for p in portfolio.get("projects",[]):
        r={"id":p["id"],"name":p["name"],**project_score(p)}
        rows.append(r)
    return sorted(rows,key=lambda x:x["strategic_value"],reverse=True)

def score_features(project):
    rows=[]
    for f in project.get("features",[]):
        rows.append({"name":f["name"],**feature_score(f)})
    return sorted(rows,key=lambda x:x["score"],reverse=True)

def apply_event(project, event):
    p=deepcopy(project)
    d=event.get("deltas",{})
    for bucket in ["scarcity","fragility"]:
        for k in list(p.get(bucket,{}).keys()):
            if k in d:
                p[bucket][k]=clamp(p[bucket][k]+d[k])
    # allow event to introduce keys if they are recognized by existing scoring dicts
    for k,v in d.items():
        if k in p.get("scarcity",{}):
            p["scarcity"][k]=clamp(p["scarcity"][k])
        if k in p.get("fragility",{}):
            p["fragility"][k]=clamp(p["fragility"][k])
    return p

def event_impact(portfolio,event):
    out=[]
    for p in portfolio.get("projects",[]):
        before=project_score(p)
        after_project=apply_event(p,event)
        after=project_score(after_project)
        out.append({
          "id":p["id"],"name":p["name"],
          "before":before["strategic_value"],
          "after":after["strategic_value"],
          "delta":round(after["strategic_value"]-before["strategic_value"],1),
          "new_action":after["action"]
        })
    return sorted(out,key=lambda x:x["delta"],reverse=True)
