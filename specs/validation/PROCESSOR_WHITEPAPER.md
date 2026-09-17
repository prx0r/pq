# A-COM Processor Calculus

Status: canonical design for AgentCom meta-kernel v3.

## Abstract

QP defines what may become canonical truth or authority. A QP Processor defines one bounded strategy for reducing the distance between current state and a QP proof obligation. Processors may search, reason, simulate, optimize, build, invoke models, run external probes, ask a human, or generate new processor proposals. They are deliberately untrusted. They cannot settle QP truth, mint authority, or write canonical state.

This gives A-COM an instruction-set-like layer for autonomous work without expanding the seven QP primitives.

## 1. Proof gap

Let canonical replayed QP state be `S_t`. A frozen Actuality Contract induces proof obligations

\[
\Omega_t = \{\omega_1,\ldots,\omega_n\}.
\]

Each obligation is

\[
\omega=(C,R,E^*,G^*,A^*,D^*)
\]

where `C` is the claim, `R` the required result, `E*` admissible evidence classes, `G*` required gate recipe, `A*` authority requirements and `D*` proof dependencies.

A proof gap remains while QP cannot derive the required judgment:

\[
\Gamma \nvdash \Pi : C \Downarrow R.
\]

The agent's job is therefore not “finish the task”. It is to reduce `Omega` until the verifier can establish the required judgments.

## 2. Processor

A processor is a typed, budgeted transducer:

\[
P_j : (S_t,\Omega_j,B_j,H_t,K_j) \rightarrow
(\Delta E_j,\Delta T_j,\Delta A_j,\Delta K_j,M_j,F_j)
\]

where:

- `S_t` is a read-only projection of QP/Oracle state;
- `Omega_j` is the set of obligations the processor claims it can address;
- `B_j` is its resource envelope;
- `H_t` is verified prior trajectory/history;
- `K_j` is explicit capability/context input;
- `Delta E` is candidate evidence;
- `Delta T` is proposed follow-up work/actions;
- `Delta A` is candidate artifacts;
- `Delta K` is newly discovered capability/context;
- `M` is measured resource/quality telemetry;
- `F` is failure information and continuation candidates.

The output deliberately contains **no canonical verdict**.

## 3. Constitutional non-interference

For every processor `P`:

\[
P(x)=y \not\Rightarrow S_{t+1}\neq S_t.
\]

Only a QP verifier/authority transition may advance state:

\[
S_{t+1}=T(S_t,\Pi) \iff Verify_\Gamma(\Pi)=PASS.
\]

Therefore a compromised web-search processor, model, optimizer, Harbor agent, `/cg` world, human predictor, or routing policy can at worst emit bad candidate work. It cannot become truth by assertion.

In code this is enforced by `ProcessorSpec(can_settle=False, canonical_write=False)`; setting either flag true is rejected at construction.

## 4. Processor contract

Each processor has a frozen manifest:

```text
id
version
kind
handles[]
requires[]
provides[]
side_effects = none | sandbox | external
determinism = deterministic | record-replay | stochastic
cost {money_minor,tokens,wall_ms,external_calls,human_minutes}
max_attempts
module_ref
fallback[]
experimental
```

The manifest is capability metadata, not trust. A processor may only enter a graph if its `requires` are satisfied by prior outputs or initial runtime capabilities.

## 5. Composition

For a processor graph `G=(V,E)` with topological order `p_1...p_m`, define the available capability set

\[
K_0=K_{initial}
\]

and

\[
K_{i+1}=K_i\cup Provides(p_i)
\]

subject to

\[
Requires(p_i)\subseteq K_i.
\]

The graph is invalid if there is a cycle, a missing capability, a ContractRoot mismatch, or an estimated resource envelope that exceeds the relevant grant/budget.

Graph resource use is initially conservatively additive:

\[
B(G)=\sum_i B(p_i).
\]

Later schedulers may use parallel critical-path time while preserving additive money/tokens/external calls.

## 6. Processor selection

For processor `p` and proof gap `omega`, the useful quantity is not nominal model intelligence or token price. A first routing objective is

\[
Score(p,\omega)=
\frac{
P(resolve\mid p,\omega,H)\cdot V(\omega)\cdot(1+IG)\cdot(1+Reuse)
}{
ExpectedResourceBurden(p,\omega)
}.
\]

For model execution the economic projection uses expected cost to verified completion:

\[
ECVC(m,\omega)=
\frac{C_{call}+E[C_{repair}]+E[C_{verify}]}{P(verified\ completion\mid m,\omega)}.
\]

GABS selects the lowest feasible ECVC subject to capability, budget, privacy, latency and QP grant constraints. Some execution share is reserved for challengers to avoid policy monoculture.

## 7. Processor families

The architecture intentionally supports processors much broader than tools:

| Family | Examples | Typical output |
|---|---|---|
| decomposition | `spec.decompose`, `proof.decompose` | proof obligations / candidate DAG |
| retrieval | `prior.retrieve`, repo search, web search | research/prior evidence |
| reuse | GitGoblin | component candidates |
| build | sandbox, repair, replace | candidate artifact |
| formal | Lean checker/prover | formal evidence |
| falsification | red-team, counterexample search | falsification evidence |
| world/simulation | `/cg`, local simulation, counterfactual | simulation evidence |
| optimization | cost/latency/search/evolution | candidate mechanisms |
| execution/eval | Harbor rollouts/evaluation | trajectories, rewards, artifacts |
| actuality | probes/readback | observations/evidence |
| human boundary | HLoop certified queue | human artifact reference |
| economic | GABS/model routing | route + grant-need signal |
| tournament | Seed0 | comparative run evidence |
| trajectory | distillation/learning | reusable verified run summaries |
| metaprocessor | module design | processor proposal |

## 8. Processors by proof type

### Structural/software proof

Typical recipe:

```text
prior.retrieve
→ reuse.gitgoblin
→ build.sandbox
→ test.hidden
→ proof.construct
→ proof.verify
```

### External actuality

```text
external action (QP PRE authority)
→ effect evidence
→ independent readback
→ proof.construct
→ proof.verify
```

The action channel and readback channel should differ where practical.

### Formal/mathematical proof

```text
formal.lean
→ independent Lean checker matrix
→ theorem artifact evidence
→ proof.construct
→ proof.verify
```

Lean proves the formal statement. QP proves the relationship between the theorem artifact and the frozen A-COM obligation.

### Optimization proof

An optimizer does not prove that its candidate is optimal by saying so. Instead:

```text
search/evolve/simulate
→ candidate set
→ frozen objective + hard constraints
→ evaluation/holdout
→ compare candidate results
→ proof of “winner under this finite frozen evaluation”
```

Global optimality requires a separate mathematical proof if claimed.

### Exploration / unknown problem

```text
verified prior retrieval
→ cheap search/reuse
→ simulation / web / repo research
→ competing causal mechanisms
→ falsification
→ targeted experiments
→ QP evidence
```

Information gain is useful even when the claim remains UNKNOWN.

### Human-exclusive proof

```text
A-task attempt / structural capability mismatch
→ runtime BlockProof
→ certified HTask
→ actual human interaction
→ opaque artifact/reference
→ actuality probe/readback
→ QP proof
```

No human task exists merely because an LLM requested one.

### Economic action

```text
proof obligation
→ GABS route
→ existing QP grant sufficient? yes → execute
                           no → certified MTask
→ actual human grant decision where policy requires
→ QP grant issuance
→ reserve action authority
→ execute
→ independent effect/readback
→ receipt
```

Wallet balances are projections. QP authority remains constitutional.

## 9. `/cg` mapping

`/cg` is a first-class world/simulation/evolution processor family. Its replayable worlds, seeded runs, quality gates and experience graph are particularly useful when a proof gap has multiple plausible mechanisms. A-COM passes the frozen obligation and candidate mechanism into the CG environment, then imports run receipts and evaluation outputs as candidate evidence. CG never becomes QP settlement.

## 10. Harbor mapping

Harbor is an optional execution/evaluation substrate:

```text
A-COM obligation
→ Harbor task/environment
→ N agent × model × attempt rollouts
→ verifier rewards + artifacts + trajectory logs
→ normalize into ProcessorOutcome
→ QP evidence / Seed0 tournament
```

Harbor's reward is an evaluator result, not QP truth. The Harbor task/test bundle must be content-addressed and referenced from the QP run if its result matters constitutionally.

## 11. New processor design

A coding agent designing a new processor must answer:

1. Which proof gaps/problem types can it reduce?
2. What exact inputs/capabilities does it require?
3. What candidate outputs does it provide?
4. What can it touch: none, sandbox, external?
5. How are stochastic/external results replayed or committed?
6. What is the maximum resource envelope?
7. What known failures cause fallback?
8. How is the processor evaluated independently?
9. What evidence proves the processor is useful across holdout tasks?
10. Can an adversarial implementation use its output fields to impersonate QP authority? If yes, redesign it.

Use `agentcom-meta new-processor <id>` as the scaffold, then run meta/red-team/tournament suites.

## 12. Accretion and recursive improvement

A processor run that fails may still add verified information:

```text
failure signature
tried mechanism
eliminated branch
new source/artifact
measured cost
unresolved gap
next candidates
```

This updates the Accretion Frontier. Future runs retrieve only verified prior trajectories. The tournament population then uses exploitation plus mutation/exploration:

\[
Population_{t+1}=Exploit(Best_t)+Mutate(Best_t)+Explore(Unseen_t).
\]

This prevents historical success from collapsing the system into one brittle recipe.

## 13. Trust boundary summary

Processors are the CPU instruction set of A-COM, but QP is the constitution. Processor diversity may grow without expanding the constitutional ontology.
