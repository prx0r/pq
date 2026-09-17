# CANONICAL — AgentCom Meta Kernel v0.5

This package is the **composition and experimentation root** for every ZIP produced in this session. Historical ZIPs are immutable environments. Their useful ideas are imported through explicit compatibility boundaries; they are never merged by copy/paste into one giant runtime.

## One sovereign chain

```text
SPECIFICATION
  -> semantic proposal (untrusted LLM)
  -> deterministic admission / source coverage
  -> frozen ContractRoot + ProofRoot
  -> Underengineer
  -> QP Processor assembly
  -> five same-root experiment lanes
  -> A-Task/OpenAI execution
  -> WorkerKit trajectory/cost/artifacts
  -> Oracle independent evidence
  -> Actuality TRUE/FALSE/UNKNOWN
  -> /qp authority + settlement
  -> Seed0 gate-first tournament
  -> verified run memory + harvest candidates
  -> next comparable run (foundation + forced mutation)
```

Only `/qp` may mint consequential authority or settle canonical truth. A processor, module, model, worker, HLoop predictor, Seed0 tournament, WorkerKit observer, or OpenAI approval may **never** become a substitute authority.

## Ownership

| Layer | Owns | Must not own |
|---|---|---|
| AgentCom v2 | spec compilation, campaigns, scheduling, composition | proof verdict, authority |
| Actuality | deterministic claim judgement from admissible evidence | action execution |
| QP | grants, truth transition, receipts, settlement/replay | strategy, implementation |
| QP Processor | bounded proof-progress transformation/search/action attempt | verdict, settlement, self-promotion |
| Underengineer | smallest proof-closing implementation surface | requirement invention |
| Seed0 | same-root policy experiments and ranking | changing ContractRoot, truth |
| A-Task | bounded work/H-task state | declaring itself DONE |
| HLoop/ALoop lineage | ask-vs-act evidence, human-policy prediction, autonomy proposals | consequence authority |
| WorkerKit | execution provenance, costs, artifacts, harvest candidates | DONE, proof validity |
| Oracle | observations, provenance, readback | strategic selection |
| QDW | expected cost-to-verified-completion routing | authority/truth |
| OpenAI Agents | cognition, tool loop, handoffs, sessions, tracing | QP authority |

## Historical package policy

All nine session ZIPs are SHA-256 pinned in `meta.lock.json`. `scripts/bootstrap.py` normalizes archive layout and materializes each into its own workspace. Never place all historical `src/` directories on one global `PYTHONPATH`; that recreates namespace collisions and makes provenance ambiguous.

Canonical current surfaces:

- composition root: `agentcom-v2`
- adversarial validation: `agentcom-testing-kernel`
- OpenAI/QP bridge: `qp-openai-native`
- production authority: external pinned `/qp`
- processor ABI: `qp.processor/0.1`

Everything else is reference science, lineage, SDK compatibility, experiment corpus, or development protocol.


## v0.5 control/economics boundaries

- **HLoop learner** owns hidden human-action prediction, calibration, OOD/risk evidence and macro candidates. It never grants consequence authority.
- **Workbench** is a view/input surface. It never stores production private keys and never marks work proven.
- **GrantBroker** owns bounded grant intent + approval workflow; an injected QP signer/vault owns cryptographic signing.
- **LiveLLM adapter** supplies candidate market facts; it does not choose truth or models.
- **QDW model router** proposes provider/model routes by expected verified-completion economics. It cannot spend money.
- **Goal-Aware Budget (GAB)** proposes exploit/explore caps; QP/wallet policy still authorizes real spend.
- **Harbor adapter** owns repeatable evaluation/rollout execution. Harbor reward/verifier output is candidate evidence; QP/Actuality remains final admission.

The human-policy learner and economic router are continuously updated only from structured events whose external outcomes can later be joined to verified receipts.


## v0.5 privacy/calibration additions

- Raw human text/code/secret payloads travel through a separate local 0600 payload store. Logs, `/api/state` and the policy learner retain only opaque reference + SHA-256 metadata.
- The human-policy learner is persistable but pending hidden predictions are deliberately not persisted; after restart a new hidden prediction must precede the answer.
- ProofDesk-lineage calibration includes Brier/ECE plus a conservative verified-failure upper bound. Calibration may block autonomy; it cannot grant authority.
- QDW routing evidence is partitioned by task family × proof class × route, preventing easy-proof success from automatically becoming a prior for consequential proof work.
- `HarborTaskCompiler` exports frozen QP obligations into standard Harbor task directories with a separate verifier environment; Harbor reward remains non-sovereign candidate evidence.


## v0.7 human autonomy constitution

Low-risk local preferences may progress `HUMAN → SHADOW → SUGGEST → GUARDED_LOCAL → AUTO_LOCAL` only from local calibrated human labels joined to verified outcomes. SECRET, IDENTITY, PHYSICAL, consequential AUTHORIZATION, and AMBIGUITY are hard-human boundaries. Autonomous decisions never become synthetic human labels. QP remains the sole authority for consequential effects.
