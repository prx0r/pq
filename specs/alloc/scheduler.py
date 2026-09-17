from __future__ import annotations
from .model import projects
from .underengineer import plan
from .experiments import live_worlds
from .resources import resource_map
from .performance import strategy_performance, family_for_project

LANE_BY_CLASS={'A_TRUTH':'FAST_TRUTH','B_DEMAND':'FAST_DEMAND','C_ECONOMIC':'ECONOMIC','D_SCARCE_STATE':'DEEP_SCARCE_STATE'}
LIVE_ROLES={'asset_campaign'}
LAB_EXCEPTIONS={'seesaw-market-lab'}

def _proposal(p,w):
    pl=plan(p['id'])
    perf={x['id']:x for x in strategy_performance()}
    family=family_for_project(p['id']); mult=perf.get(family,{}).get('scheduler_multiplier',1.0) if family else 1.0
    return {'project_id':p['id'],'name':p['name'],'world':w['id'],'class':w['class'],'lane':LANE_BY_CLASS[w['class']],
      'world_score':w['score'],'project_priority':pl['priority_score'],'strategy_family':family,'performance_multiplier':mult,'combined_score':round(w['score']*max(0.1,pl['priority_score'])*mult,4),
      'resources':w.get('resources',[]),'first_real_moat_event':pl['first_real_moat_event'],'next_step':pl['next_step'],
      'learning_goal':p.get('experiment_strategy',{}).get('learning_goal'),'strategic_role':p['strategic_role'],
      'required_components_now':pl.get('required_components_now',[])}

def proposals():
    out=[]
    for p in projects():
        if p['strategic_role'] not in LIVE_ROLES and p['id'] not in LAB_EXCEPTIONS: continue
        for w in live_worlds(p['id']): out.append(_proposal(p,w))
    out.sort(key=lambda x:(-x['combined_score'],x['project_id'],x['world']))
    return out

def schedule():
    rm=resource_map(); used={}; selected=[]; rejected=[]; lane_count={}; chosen_projects=set()
    for x in proposals():
        if x['project_id'] in chosen_projects:
            rejected.append({**x,'reason':'project already has a higher-ranked live experiment'}); continue
        conflict=None
        for rid in x['resources']:
            r=rm.get(rid,{})
            if r.get('parallelism')==1 and used.get(rid,0)>=1: conflict=rid; break
        if conflict:
            rejected.append({**x,'reason':f'resource bottleneck: {conflict}'}); continue
        if lane_count.get(x['lane'],0)>=2:
            rejected.append({**x,'reason':f'lane capacity: {x["lane"]}'}); continue
        selected.append(x); chosen_projects.add(x['project_id']); lane_count[x['lane']]=lane_count.get(x['lane'],0)+1
        for rid in x['resources']: used[rid]=used.get(rid,0)+1
    preflight=[{'project_id':x['project_id'],'world':'internal_simulation','proof_ceiling':'SIMULATION_ONLY','purpose':f'rank/pressure-test {x["world"]} before consuming scarce resource'} for x in selected]
    pulled={}
    for x in selected:
        for c in x.get('required_components_now',[]): pulled.setdefault(c,[]).append(x['project_id'])
    support=[]
    for p in projects():
        if p['strategic_role']=='asset_campaign' or p['id'] in LAB_EXCEPTIONS: continue
        if p['id'] in pulled or any(c in pulled for c in p.get('components',[])):
            support.append({'project_id':p['id'],'name':p['name'],'role':p['strategic_role'],'pulled_by':sorted(set(sum([v for k,v in pulled.items() if k==p['id'] or k in p.get('components',[])],[])))})
    return {'rule':'External experiment slots belong to scarce-asset campaigns. Infrastructure cannot outbid a campaign for a store/account/permission; it is pulled as support. Seesaw Market Lab is the explicit calibration-lab exception.',
      'live_queue':selected,'simulation_preflight':preflight,'resource_allocations':used,'pulled_infrastructure':support,
      'blocked_or_deferred':rejected[:30],'strategy_performance':strategy_performance()}
