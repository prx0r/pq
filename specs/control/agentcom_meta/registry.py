from __future__ import annotations
import json
from dataclasses import fields
from pathlib import Path
from .processor import ProcessorManifest,CostPrior

class ProcessorRegistry:
    def __init__(self):
        self._items:dict[str,ProcessorManifest]={}
        self._aliases:dict[str,str]={}
        self._providers:dict[str,list[str]]={}
    def register(self,m:ProcessorManifest):
        m.validate()
        if m.id in self._items: raise ValueError(f"duplicate-processor:{m.id}")
        self._items[m.id]=m
        for alias in m.legacy_aliases:
            if alias in self._aliases and self._aliases[alias]!=m.id:
                raise ValueError(f"ambiguous-legacy-alias:{alias}:{self._aliases[alias]}:{m.id}")
            self._aliases[alias]=m.id
        for p in m.provides:self._providers.setdefault(p,[]).append(m.id)
        return m
    def get(self,id_or_alias:str)->ProcessorManifest:
        key=self._aliases.get(id_or_alias,id_or_alias)
        if key not in self._items: raise KeyError(key)
        return self._items[key]
    def providers(self,capability:str)->tuple[ProcessorManifest,...]:
        return tuple(self._items[x] for x in self._providers.get(capability,()))
    def all(self):return tuple(sorted(self._items.values(),key=lambda x:x.id))
    def resolve_alias(self,alias:str)->str|None:return self._aliases.get(alias)
    @classmethod
    def from_dir(cls,path:str|Path):
        r=cls()
        for p in sorted(Path(path).rglob("*.processor.json")):
            d=json.loads(p.read_text())
            cost=CostPrior(**d.pop("cost",{}))
            for k in ("requires","provides","proof_classes","evidence_channels","side_effects","failure_codes","fallback_tags","mutation_knobs","prohibitions","legacy_aliases"):
                if k in d:d[k]=tuple(d[k])
            r.register(ProcessorManifest(cost=cost,**d))
        return r

# Package-local registry for wheel/standalone SDK users.
def stdlib_registry():
    from .data import packaged_processors
    return ProcessorRegistry.from_dir(packaged_processors())
