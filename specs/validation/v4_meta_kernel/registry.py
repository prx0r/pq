from __future__ import annotations
import json
from pathlib import Path
from .models import ProcessorSpec, Cost

class ProcessorRegistry:
    def __init__(self): self._p={}
    def register(self,p:ProcessorSpec):
        if p.id in self._p: raise ValueError('duplicate processor '+p.id)
        self._p[p.id]=p; return p
    def get(self,id): return self._p[id]
    def ids(self): return tuple(sorted(self._p))
    def by_gap(self,kind): return tuple(p for p in self._p.values() if kind in p.handles or '*' in p.handles)
    def load_dir(self,path):
        for f in sorted(Path(path).glob('*.json')):
            x=json.loads(f.read_text()); x['cost']=Cost(**x.get('cost',{})); self.register(ProcessorSpec(**x))
        return self
    def validate_graph(self,ids,initial=frozenset({'contract','budget','history'})):
        available=set(initial)
        for pid in ids:
            p=self.get(pid); missing=set(p.requires)-available
            if missing: raise ValueError(f'{pid}: missing inputs {sorted(missing)}')
            for group in p.requires_any:
                if not (set(group) & available):
                    raise ValueError(f'{pid}: requires one of {sorted(group)}')
            available.update(p.provides)
        return frozenset(available)

def builtin_registry():
    return ProcessorRegistry().load_dir(Path(__file__).resolve().parents[1]/'processors')
