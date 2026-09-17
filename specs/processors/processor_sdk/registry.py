from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from .model import ProcessorSpec, ResourceEstimate, processor_root

class ProcessorRegistry:
    def __init__(self):
        self._by_id: dict[str, tuple[ProcessorSpec,str]] = {}

    def register(self, spec: ProcessorSpec) -> str:
        if spec.id in self._by_id:
            raise ValueError(f"immutable processor id already registered: {spec.id}")
        root=processor_root(spec)
        self._by_id[spec.id]=(spec,root)
        return root

    def get(self, processor_id: str) -> ProcessorSpec:
        try:
            return self._by_id[processor_id][0]
        except KeyError as e:
            raise KeyError(f"unknown processor {processor_id}") from e

    def root(self, processor_id: str) -> str:
        return self._by_id[processor_id][1]

    def list(self) -> list[ProcessorSpec]:
        return [x[0] for x in self._by_id.values()]

    def matching(self, tags: set[str]) -> list[ProcessorSpec]:
        rows=[]
        for spec in self.list():
            if not spec.handles:
                continue
            if tags.intersection(spec.handles):
                rows.append(spec)
        return rows

    def manifest(self):
        return [
            {"id":s.id,"root":self.root(s.id),"kind":s.kind,"version":s.version}
            for s in sorted(self.list(),key=lambda x:x.id)
        ]

    def load_json(self, path: str | Path) -> list[str]:
        payload=json.loads(Path(path).read_text())
        items=payload if isinstance(payload,list) else payload.get("processors",[])
        roots=[]
        for d in items:
            estimate=d.get("default_estimate") or {}
            spec=ProcessorSpec(
                id=d["id"],version=d["version"],kind=d["kind"],
                description=d.get("description",""),
                input_types=tuple(d.get("input_types") or ()),
                output_types=tuple(d.get("output_types") or ()),
                handles=tuple(d.get("handles") or ()),
                capabilities=tuple(d.get("capabilities") or ()),
                proof_outputs=tuple(d.get("proof_outputs") or ()),
                deterministic=bool(d.get("deterministic",False)),
                consequence_free=bool(d.get("consequence_free",True)),
                default_estimate=ResourceEstimate(**estimate),
                fallback_pack=d.get("fallback_pack"),
                mutation_axes=tuple(d.get("mutation_axes") or ()),
                evaluator_contract=d.get("evaluator_contract"),
                implementation_hash=d.get("implementation_hash","external"),
            )
            roots.append(self.register(spec))
        return roots

