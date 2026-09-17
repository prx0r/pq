from __future__ import annotations
import argparse,json
from pathlib import Path
from dataclasses import asdict
from .registry import ProcessorRegistry,stdlib_registry
from .planner import ProofNeed,plan_processors
from .packages import materialize
from .processor_science import recipe_for,PROCESSOR_FAMILIES
from .data import packaged_modules
from .harbor import HarborTaskCompiler,HarborQPTask

def _registry(root):
    return ProcessorRegistry.from_dir(Path(root)/'processors') if root else stdlib_registry()

def _module_rows(root=None):
    base=Path(root)/'modules' if root else packaged_modules()
    out=[]
    for p in sorted(base.glob('*/qp.module.json')):
        d=json.loads(p.read_text());out.append(d)
    return out

def main(argv=None):
    p=argparse.ArgumentParser(prog='agentcom-meta');sp=p.add_subparsers(dest='cmd',required=True)
    b=sp.add_parser('bootstrap');b.add_argument('--root',required=True,help='full meta-ZIP root containing archives/ and meta.lock.json');b.add_argument('--out',default='workspace')
    l=sp.add_parser('processors');l.add_argument('--root')
    m=sp.add_parser('modules');m.add_argument('--root')
    q=sp.add_parser('plan');q.add_argument('capabilities',nargs='+');q.add_argument('--root');q.add_argument('--initial',nargs='*',default=[])
    rr=sp.add_parser('recipe');rr.add_argument('--proof');rr.add_argument('--problem')
    he=sp.add_parser('harbor-export');he.add_argument('spec_json');he.add_argument('--out',required=True)
    a=p.parse_args(argv)
    if a.cmd=='bootstrap':
        root=Path(a.root);print(json.dumps(materialize(root/'meta.lock.json',root/'archives',Path(a.out)),indent=2));return 0
    if a.cmd=='modules':
        print(json.dumps(_module_rows(a.root),indent=2));return 0
    if a.cmd=='recipe':
        print(json.dumps({'proof_class':a.proof,'problem_type':a.problem,'families':recipe_for(proof_class=a.proof,problem_type=a.problem),'family_docs':PROCESSOR_FAMILIES},indent=2));return 0
    if a.cmd=='harbor-export':
        d=json.loads(Path(a.spec_json).read_text());spec=HarborQPTask(**d);print(json.dumps(HarborTaskCompiler().export(spec,a.out),indent=2));return 0
    r=_registry(getattr(a,'root',None))
    if a.cmd=='processors':
        print(json.dumps([{'id':m.id,'kind':m.kind,'requires':m.requires,'provides':m.provides,'proof_classes':m.proof_classes,'manifest_id':m.manifest_id} for m in r.all()],indent=2));return 0
    if a.cmd=='plan':
        print(json.dumps(asdict(plan_processors(ProofNeed('cli',tuple(a.capabilities)),r,initial_capabilities=a.initial)),indent=2));return 0
    return 2
