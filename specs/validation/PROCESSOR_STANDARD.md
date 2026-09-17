# QP Processor Standard v1

A processor is an installable strategy module for reducing one or more QP proof gaps. It is **not** a verifier, authority root, task status owner, or canonical state store.

## Normative invariants

1. `can_settle` MUST be false.
2. `canonical_write` MUST be false.
3. Consequential external effects MUST pass a QP pre-action authority boundary outside the processor.
4. Outputs MUST be data/artifact references, not caller-declared QP verdicts.
5. All money is integer minor units; unknown prices/usage remain unknown rather than guessed zero.
6. All processor graphs bind one frozen `ContractRoot`.
7. Stochastic/external processors MUST emit a replay/commitment envelope adequate to identify their actual run.
8. Human and money escalation processors can only request/carry runtime-certified BlockProofs; they cannot fabricate HTask/MTask instances.
9. A processor that consumes history MUST restrict canonical learning to verified trajectories.
10. New processor promotion requires independent tests and at least one holdout/tournament comparison.

## Manifest

```json
{
  "id": "harbor.rollout",
  "version": "1.0.0",
  "kind": "execution_evaluator",
  "handles": ["exploration", "optimization", "failure"],
  "requires": ["contract"],
  "provides": ["trajectory_evidence", "candidate_artifact"],
  "side_effects": "sandbox",
  "determinism": "record-replay",
  "cost": {"tokens": 3500, "wall_ms": 12000},
  "max_attempts": 5,
  "module_ref": "optional:harbor-framework/harbor",
  "fallback": ["build.sandbox"],
  "experimental": true,
  "can_settle": false,
  "canonical_write": false
}
```

## Runtime input

```text
ProcessorRequest {
  processor_id
  contract_root
  gap
  inputs
  budget
  prior_run_ids
}
```

## Runtime output

```text
ProcessorOutcome {
  status = PROPOSED | OBSERVED | BLOCKED | FAILED
  evidence[]
  task_proposals[]
  artifact_refs[]
  discovered_capabilities[]
  notes[]
}
```

Receipt/authority fields are intentionally absent.

## Problem classes

Recommended normalized problem labels are:

```text
implementation
integration
validation
failure
optimization
exploration
external
math
protocol
human_exclusive
economic_action
unknown
proof_gap
```

Projects can add domain tags without changing these kernel classes.

## Promotion ladder

```text
PROPOSED processor
→ schema + constitutional lint
→ unit tests
→ adversarial tests
→ replay/fixture tests
→ same-ContractRoot Seed0 tournament
→ holdout tasks
→ QP-governed module promotion
```

A processor never self-promotes based on its own benchmark output.

## V4 evidence-polymorphic inputs

A processor may have hard conjunctive `requires` and explicit OR-groups in `requires_any`. Every `requires_any` group must have at least one capability available before the processor can execute. This is used by `proof.construct`: it always requires the frozen contract and at least one declared evidence family. The registry rejects a graph that reaches proof construction with no evidence producer.
