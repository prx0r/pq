from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, textwrap, os

@dataclass(frozen=True)
class HarborTaskSpec:
    task_id: str
    instruction: str
    category: str
    tags: tuple[str,...]
    agent_timeout_sec: float = 1800
    verifier_timeout_sec: float = 120
    cpus: int = 1
    memory_mb: int = 2048
    storage_mb: int = 10240
    verifier_py: str = "assert True"
    dockerfile: str = "FROM python:3.13-slim\nWORKDIR /app\n"

class HarborTaskExporter:
    def export(self,spec:HarborTaskSpec,dest:Path)->Path:
        task=dest/spec.task_id
        (task/"environment").mkdir(parents=True,exist_ok=True)
        (task/"tests").mkdir(parents=True,exist_ok=True)

        (task/"instruction.md").write_text(spec.instruction.rstrip()+"\n")
        (task/"environment/Dockerfile").write_text(spec.dockerfile.rstrip()+"\n")
        (task/"tests/test_outputs.py").write_text(
            "def test_task():\n"
            + textwrap.indent(spec.verifier_py.strip(),"    ")
            + "\n"
        )
        (task/"tests/test.sh").write_text(textwrap.dedent('''\
            #!/bin/bash
            set -e
            python -m pip install -q pytest
            if pytest -q /tests/test_outputs.py; then
              echo '{"score":1.0}' > /logs/verifier/reward.json
            else
              echo '{"score":0.0}' > /logs/verifier/reward.json
              exit 1
            fi
        '''))
        (task/"tests/test.sh").chmod((task/"tests/test.sh").stat().st_mode|0o111)

        def q(s): return json.dumps(str(s))
        tags=", ".join(q(x) for x in spec.tags)
        toml=(
            'schema_version = "1.4"\n\n'
            '[task]\n'
            f'name = {q("agentcom/"+spec.task_id)}\n'
            'version = "1.0.0"\n'
            f'description = {q("A-COM processor shadow-world trial")}\n\n'
            '[metadata]\n'
            f'category = {q(spec.category)}\n'
            f'tags = [{tags}]\n\n'
            '[agent]\n'
            f'timeout_sec = {float(spec.agent_timeout_sec)}\n\n'
            '[verifier]\n'
            f'timeout_sec = {float(spec.verifier_timeout_sec)}\n\n'
            '[environment]\n'
            f'cpus = {int(spec.cpus)}\n'
            f'memory_mb = {int(spec.memory_mb)}\n'
            f'storage_mb = {int(spec.storage_mb)}\n'
        )
        (task/"task.toml").write_text(toml)
        return task

    def export_processor_trial(
        self, *,
        processor_id:str, processor_root:str, contract_root:str,
        obligation_id:str, instruction:str, verifier_py:str, dest:Path,
        tags:tuple[str,...]=("acom","processor","shadow-world"),
    )->Path:
        spec=HarborTaskSpec(
            task_id=(processor_id.replace(".","-")+"-"+obligation_id.replace(".","-")),
            instruction=(
                instruction.rstrip()
                + "\n\nFrozen metadata:\n"
                + f"- processor_root: {processor_root}\n"
                + f"- contract_root: {contract_root}\n"
                + f"- proof_obligation: {obligation_id}\n"
                + "Do not alter the evaluator or claim success outside the requested artifact.\n"
            ),
            category="agentic-evaluation",
            tags=tags,
            verifier_py=verifier_py,
        )
        return self.export(spec,dest)
