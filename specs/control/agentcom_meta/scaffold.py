from __future__ import annotations
import json,re
from pathlib import Path

def scaffold_processor(root:str|Path,processor_id:str,*,kind="analyze"):
    if not re.fullmatch(r"[a-z0-9_.-]+\.[a-z0-9_.-]+",processor_id):raise ValueError("invalid-processor-id")
    safe=processor_id.replace(".","_")
    d=Path(root)/safe;d.mkdir(parents=True,exist_ok=False)
    manifest={
      "id":processor_id,"version":"0.1.0","kind":kind,"requires":[],"provides":[],
      "proof_classes":["Q2"],"evidence_channels":[],"side_effects":[],"authority_required":False,
      "deterministic":True,"seed_required":False,"pure":True,"timeout_s":30,
      "cost":{"money":0,"tokens":0,"wall_seconds":0.1,"external_calls":0,"human_seconds":0,"uncertainty":0.1},
      "failure_codes":[],"fallback_tags":[],"mutation_knobs":[],
      "prohibitions":["settle","mint-authority","self-validate"],"legacy_aliases":[],
      "description":"TODO: define one bounded proof-progress transformation."
    }
    (d/f"{safe}.processor.json").write_text(json.dumps(manifest,indent=2,sort_keys=True))
    (d/"README.md").write_text(f"# {processor_id}\n\nDefine inputs, outputs, evidence, costs, failure modes, mutation knobs and negative controls before implementation.\n")
    (d/"processor.py").write_text("def run(inputs, context):\n    return {'outputs':{}, 'evidence':[], 'capabilities_added':[]}\n")
    (d/"test_processor.py").write_text("def test_negative_control():\n    # Replace with a falsifier that the processor must not bypass.\n    assert True\n")
    return d
