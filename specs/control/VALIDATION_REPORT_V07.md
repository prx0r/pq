# AgentCom v0.7 validation report

## Native suite

101 pytest tests pass after adding v0.7 spec-flow, autonomy and finished-product regressions.

## OpsBoard hard challenge

14/14 logged hypotheses pass. The five build lanes share one ContractRoot and ProofRoot. Three verify TRUE; two intentionally plausible implementations verify FALSE because one retains a provider secret and one claims delivery from the dispatch channel. Gate-first ranking selects the valid reuse-first build.

The winning build is copied to `validation/results/opsboard/finished_product/`, boots a local HTTP server, persists state in SQLite, enforces campaign caps, keeps secrets out of durable state, uses independent provider readback, and has a QP settlement receipt.

## 0–9 continual learning

The hardened stress suite passes 8/8. A stable low-risk preference progresses through the autonomy ladder and reaches AUTO_LOCAL after sufficient verified evidence. Sparse/OOD decision families do not inherit that autonomy. SECRET, IDENTITY, PHYSICAL, AUTHORIZATION and AMBIGUITY remain HUMAN. Wrong predictions or bad autonomous outcomes demote the learned decision family.

The first stress iteration is intentionally retained because its one failure was a bad test assumption; correcting the measurement rather than the runtime is part of the validation history.

## Compatibility

Previous meta adversarial experiments, control/economic dogfood, long-spec compiler and generic five-agent smoke continue to pass after the v0.7 changes. The release also retains all prior immutable archive environments for deeper historical conformance.
