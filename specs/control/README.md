# AgentCom Control + Economics v0.7

v0.7 keeps the v0.6 proof/processor stack and adds a harder finished-product dogfood (OpsBoard) plus continual 0–9 human-policy learning wired into the Workbench. See `VALIDATION_REPORT_V07.md` and `ITERATION_HISTORY_V07.md`.

---

# AgentCom Canonical Control + Economic Kernel v0.5

This ZIP is the current composition/experimentation root for the AgentCom/QP work built in this conversation. It keeps every earlier ZIP isolated and hash-pinned, and adds the missing control surfaces needed for real autonomous work: **QP Processor science, H-tasks/HLoop learning, mobile workbench, wallet/grants, QDW+LiveLLM economic routing, Harbor evaluation, and module manifests**.

## The loop

```text
LONG TECHNICAL SPEC
  ↓
untrusted LLM semantic proposal
  ↓
deterministic source / coverage / safety admission
  ↓
ContractRoot + QP ProofRoot
  ↓
Underengineer
  ↓
QP Processor graph
  ↓
5 same-root Seed0 lanes
  ↓
OpenAI Agents / A-Task execution
  ↓
┌─ genuine human boundary? → hidden 0–9 prediction → mobile H-task
│                            raw payload → sealed 0600 channel
│                            unrelated branches continue
└─ otherwise continue
  ↓
QDW + LiveLLM route models/runtimes by expected verified cost
  ↓
QP grant immediately before spend/external consequence
  ↓
WorkerKit trajectory / costs / artifacts
  ↓
Oracle independent evidence
  ↓
Actuality TRUE / FALSE / UNKNOWN
  ↓
QP receipt + replay settlement
  ↓
Seed0 gate-first ranking + Harbor experiments
  ↓
RunBank / harvest / HLoop outcome join
  ↓
next run = verified foundation + forced mutation
```

## Zero-install checks

```bash
./scripts/doctor.py
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/control_plane_dogfood.py
PYTHONPATH=src python scripts/five_agent_smoke.py
PYTHONPATH=src python scripts/integration_spec_smoke.py
```

Inspect the SDK:

```bash
PYTHONPATH=src python -m agentcom_meta processors
PYTHONPATH=src python -m agentcom_meta modules
PYTHONPATH=src python -m agentcom_meta recipe --proof Q6 --problem consequential_action
```

A prebuilt wheel is generated in `dist/` by the release script.

## QP Processors

A proof says **what must be established**. A processor is a bounded mechanism that attempts to make progress toward it.

Processor families include:

`transform · analyze · search · simulate · optimize · experiment · reuse · synthesize · repair · probe · route · escalate · act · harvest`

Read:

- `QP_PROCESSOR_SCIENCE.md`
- `docs/PROCESSOR_MATHEMATICS.md`
- `docs/PROCESSOR_SELECTION_MATRIX.md`
- `docs/PROCESSOR_AUTHORING_GUIDE.md`
- `docs/PROCESSOR_RECIPES.md`

The standard bank includes Underengineer, GitGoblin reuse, problem/company graphs, web search, world simulation, code build/repair, Oracle probes, LiveLLM, QDW model routing, HLoop escalation, ProofDesk-lineage calibration, wallet grants, QP-guarded external action, Harbor export/eval, Seed0 tournament, A-Task execution and harvest.

## Human tasks / 0–9 control

Only six H-task classes exist:

`AUTHORIZATION · SECRET · PREFERENCE · PHYSICAL · IDENTITY · AMBIGUITY`

Before a task is shown, the learner records a hidden distribution over keys 0–9. After the human acts, that prediction is joined to the key, human time and later verified outcome. Accuracy, Brier, ECE, OOD and a conservative verified-failure bound control local autonomy eligibility.

**Predictability never becomes authority.** A perfectly predictable approval still requires the QP grant path for a consequential action.

Raw pasted text/code/secrets are not written into learner state or ordinary logs. They go to a separate local 0600 payload store; telemetry contains only reference/hash metadata.

Read `docs/HUMAN_CONTROL.md` and `docs/HTASK_RUNTIME.md`.

## Mobile Workbench

Run:

```bash
PYTHONPATH=src agentcom-workbench
```

or, for a trusted LAN/VPN only:

```bash
AGENTCOM_WORKBENCH_HOST=0.0.0.0 PYTHONPATH=src agentcom-workbench
```

The included mobile-first installable PWA has:

- 0–9 drum-pad controls + haptics where supported;
- bounded H-task/options card;
- CHAT / CODE / SECRET payload composer;
- continual-policy metrics;
- proposed processor/model runs with money/token/time/proof/authority fields;
- approve/deny buttons;
- QP/wallet state;
- agent logs with raw payload exclusion.

It is intentionally much smaller than `/qdw-workbench`. The reference server has no production auth/TLS; do not expose it to the public internet.

## Wallet + grants

Human run approval creates status:

`HUMAN_APPROVED_PENDING_QP`

not `AUTHORIZED`.

A run becomes `QP_AUTHORIZED` only after a valid grant reference is linked. The production private signer/vault is outside this runtime. The test suite exercises the exact reviewed QP Ed25519 grant implementation.

Read `docs/WALLET_AND_GRANTS.md` and `docs/ECONOMIC_CONTROL_PLANE.md`.

## QDW + LiveLLM + GAB

LiveLLM supplies provenance-bearing current model/provider market facts. QDW combines those with empirical **task-family × proof-class × route** outcomes and minimizes expected cost to verified completion. GAB proposes exploit/explore caps; it cannot spend.

This prevents a cheap model's Q2 success from becoming an unearned Q6 prior.

## Harbor

Harbor is integrated as an **evaluation processor laboratory**. `HarborTaskCompiler` exports a frozen QP obligation into a standard local Harbor task with separate verifier environment and proof metadata. Harbor can then compare agents/models/environments and generate rollouts; AgentCom/QP decides whether trial outputs are admissible proof.

```bash
PYTHONPATH=src python -m agentcom_meta harbor-export examples/harbor_qp_task.json --out /tmp/harbor-dataset
```

Read `docs/HARBOR.md` and `docs/HARBOR_QP_EXPORT.md`.

## Module packs

`modules/` contains explicit manifests for:

- human control
- QDW
- LiveLLM
- Harbor
- ProofDesk calibration lineage
- wallet/QP authority
- company graph
- Seed0
- Underengineer

New `/cg`, `/xmr`, `/cmail`, `/shopify`, security or other domain packs should add processors/schema/adapters through the same boundary rather than create another orchestrator.

## Historical environments

Earlier session ZIPs remain immutable under `archives/` and are pinned by `meta.lock.json`. `scripts/bootstrap.py` extracts them into separate workspaces to avoid Python/JS namespace collisions. Production authority remains the pinned external `/qp` repo.

## Release truth

See `VALIDATION_REPORT_V05.md` and `runs/CONTROL_PLANE_JOURNAL.md` for executed evidence and explicit `NOT_CONFIGURED` production gates.
