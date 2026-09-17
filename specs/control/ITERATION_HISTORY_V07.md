# v0.7 iteration history

## Baseline

v0.6 began green at 88/88 native tests. v0.7 deliberately kept those tests before adding new behavior.

## Harder product challenge: OpsBoard

A longer product spec was compiled into frozen proof obligations, then five isolated builders produced runnable implementations. The independent verifier rejected the secret-leaking and same-channel-delivery versions before economics. The valid reuse-first lane won and was promoted into a runnable local HTTP product.

The full OpsBoard journal is under `validation/results/opsboard/` and currently passes 14/14 hypotheses.

## Human-policy stress iteration 1 — one red test

The first 0–9 stress run passed 7/8. The failure was in the persistence test: it asserted that no pending prediction existed *after* asking the reloaded model to make a fresh prediction. The model was correct; the measurement was wrong. The failed journal is preserved under `validation/results/human_policy_stress_iteration_01_failed/`.

Action: inspect `pending` immediately after reload, then create the fresh hidden prediction. Rerun: 8/8 PASS.

## Autonomy hardening

Goal ambiguity was added to the hard-human constitution. Even a perfectly predictable ambiguity cannot silently change the user's goal.

Autonomy promotion is local to the decision family rather than global user accuracy. A learned default-view preference cannot donate confidence to a different preference or to secrets/authorization.

A bad autonomous outcome now demotes that local decision family without becoming a synthetic human label.

## Workbench stale-prediction bug

During integration review, `present_or_auto()` could leave an AUTO_LOCAL hidden prediction in the pending-human-label map forever, because no human keypress would consume it.

Action: AUTO_LOCAL decisions now remove their hidden prediction from the pending human-label queue immediately. Their subsequent results are tracked through autonomous-outcome monitoring, not self-generated training labels. Added a regression test.

## Recovery behavior

When a proof is FALSE, the processor graph can now demonstrate two bounded fallback paths in the dogfood journal:

- failure → problem graph → web search → world simulation;
- artifact + failure → local repair.

This is preferable to reflexively escalating to a human.

## Current state

- native pytest: 101 tests
- OpsBoard end-to-end dogfood: 14/14
- continual human-policy stress: 8/8 after preserving the failed first iteration
- meta adversarial experiments: 23/23
- control/economic dogfood: 9/9
- legacy long-spec and five-agent smoke: PASS
