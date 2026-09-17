from __future__ import annotations
from dataclasses import asdict
from typing import Any, Protocol
from .model import ProcessorSpec, ProcessorRun, ProcessorFailure, processor_root, run_root
from .registry import ProcessorRegistry

class ProcessorDriver(Protocol):
    def run_processor(
        self,
        *,
        spec: ProcessorSpec,
        inputs: dict[str,Any],
        budget: dict[str,Any],
        context: dict[str,Any],
    ) -> dict[str,Any]: ...

class ProcessorExecutor:
    """Reference execution boundary.

    The driver may be OpenAI Agents, OpenCode, Hermes, a local model, or a
    deterministic simulator. It is untrusted cognition. The executor records
    the attempt; QP settlement remains separate.
    """
    def __init__(self, registry: ProcessorRegistry, driver: ProcessorDriver):
        self.registry=registry
        self.driver=driver

    def execute(
        self, *,
        processor_id: str,
        contract_root: str,
        obligation_ids: list[str],
        inputs_root: str,
        world_root: str | None,
        policy_root: str,
        budget: dict[str,Any],
        inputs: dict[str,Any],
        context: dict[str,Any],
    ) -> tuple[ProcessorRun, dict[str,Any]]:
        spec=self.registry.get(processor_id)
        run=ProcessorRun(
            processor_root=self.registry.root(processor_id),
            processor_id=processor_id,
            contract_root=contract_root,
            proof_obligation_ids=list(obligation_ids),
            inputs_root=inputs_root,
            world_root=world_root,
            policy_root=policy_root,
            budget=dict(budget),
            status="RUNNING",
        )
        try:
            out=self.driver.run_processor(
                spec=spec,inputs=inputs,budget=budget,context=context
            )
            run.status="OUTPUT_PRODUCED"
            run.outputs_root="sha256:"+__import__("hashlib").sha256(
                __import__("json").dumps(out,sort_keys=True,separators=(",",":")).encode()
            ).hexdigest()
            run.metrics=dict(out.get("metrics") or {})
            return run,out
        except Exception as e:
            run.status="FAILED"
            run.failure={"code":"DRIVER_ERROR","detail":repr(e)}
            return run,{"error":repr(e)}

class RecordedProcessorDriver:
    def __init__(self, outputs: dict[str,dict[str,Any]]):
        self.outputs=outputs
    def run_processor(self, *, spec, inputs, budget, context):
        if spec.id not in self.outputs:
            raise RuntimeError(f"no recorded output for {spec.id}")
        return __import__("json").loads(__import__("json").dumps(self.outputs[spec.id]))
