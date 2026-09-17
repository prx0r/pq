# A-COM

## Cryptographic Autonomous Computation Protocol

### 0. Core thesis

Assume:

$$
Cost(Cognition) \rightarrow 0
$$

Agents, models, simulations, search, planning, hypothesis generation, code generation and adversarial critique become effectively unlimited.

The scarce thing is no longer cognition.

The scarce thing is:

> **permission for cognition to change consequential state.**

Therefore A-COM separates:

$$
\boxed{Cognition \neq Truth \neq Authority}
$$

**Cognition** may be unlimited and untrusted.

**Truth** may enter canonical state only through explicit evidence contracts and deterministic gates.

**Authority** may produce external consequences only through explicit cryptographic grants.

A-COM is the hard layer between the three.

---

# 1. The microprocessor analogy

A-COM should be thought of as an **instruction set for autonomous computation**.

An LLM is not the operating system.

An LLM is a speculative execution unit.

It may produce one million candidate continuations.

A-COM exposes a tiny legal instruction set:

```text
OBSERVE
PROPOSE
EXECUTE
VERIFY
RESOLVE
PROMOTE
CHALLENGE
GRANT
REVOKE
```

Everything eventually becomes one of these operations.

An agent cannot invent a new way of mutating canonical state merely because it wrote convincing prose.

Every operation has:

```text
typed input
canonical pre-state
explicit program
evidence
authority
required gates
deterministic result
canonical post-state
receipt
```

The primitive is therefore:

$$
\boxed{
S_{t+1} =
T(S_t,P)
\iff
\bigwedge_i G_i(S_t,P,E,A)=PASS
}
$$

where:

* `S` = canonical state
* `P` = untrusted proposal
* `E` = evidence
* `A` = authority/grant
* `G` = deterministic gates

---

# 2. The seven canonical objects

Do not keep inventing domain-specific primitives.

A-COM needs seven core objects:

```text
STATE
CLAIM
EVIDENCE
TASK
RUN
GATE
GRANT
```

Everything else is composition.

## STATE

Canonical world state at a cursor.

```yaml
state:
  cursor: 18471
  rules_commit: 4ef91a...
  event_root: ...
  state_root: ...
```

State is always replayable from the event log.

## CLAIM

A typed proposition about reality.

```yaml
claim:
  id: memory.hbm.gap
  statement: "Qualified HBM demand exceeds effective qualified supply."
  domain: semiconductors.memory
  result_type: bool3
  valid_from: ...
  valid_until: ...
```

Internally:

```text
TRUE
FALSE
UNKNOWN
```

## EVIDENCE

An immutable typed observation.

```yaml
evidence:
  id: sha256:...
  metric: qualified_hbm_supply
  value: 102
  unit: normalized_capacity
  as_of: 2026-09-12

  source:
    class: producer_guidance
    artifact_hash: sha256:...
```

Evidence does not itself alter truth.

## TASK

A requested state improvement.

```yaml
task:
  id: ...
  kind: RESOLVE_CLAIM
  target: memory.hbm.gap

  acceptance:
    claim_state: not_UNKNOWN
    min_sources: 2
    gate: hbm-gap-v1
```

## RUN

A concrete attempt at a task.

```yaml
run:
  task: ...
  worker: ...
  model: ...
  inputs_root: ...
  events_root: ...
  outputs_root: ...
  tokens: ...
  cost: ...
  duration: ...
```

## GATE

Deterministic acceptance logic.

```yaml
gate:
  id: hbm-gap-v1
  runtime: wasm
  program_hash: ...
  input_schema_hash: ...
```

## GRANT

Capability to create an external consequence.

```yaml
grant:
  subject: worker17
  capability: trading.swap

  constraints:
    max_value: 500
    asset: USDC
    calls: 3

  predicates:
    - trade.thesis_alive == TRUE

  expiry: ...
  signature: ...
```

---

# 3. One canonical output: TransitionReceipt

Everything meaningful emits the same artifact.

```json
{
  "protocol": "acom/0.1",
  "transition_type": "RESOLVE",

  "subject": "claim:memory.hbm.gap",

  "state_before": "...",
  "proposal": "...",

  "inputs_root": "...",
  "evidence_root": "...",

  "program": {
    "runtime": "wasm",
    "hash": "..."
  },

  "gates": [
    {
      "id": "hbm-gap-v1",
      "result": "PASS",
      "proof": "..."
    }
  ],

  "grant": null,

  "run": {
    "worker": "researcher-17",
    "cost": 0.042,
    "duration_ms": 84412,
    "event_root": "..."
  },

  "state_after": "...",

  "signature": "..."
}
```

Canonical JSON → hash → sign.

This is the shared interchange primitive for:

```text
atask
aloop
CG
WorkerKit
MW
Killfeed
Pearl-backed inference
future systems
```

---

# 4. The hard kernel

The kernel should know almost nothing.

It should implement only:

```text
canonical serialization
content hashing
stable IDs
append-only events
state replay
state roots
schema validation
gate execution
grant verification
receipt construction
transition acceptance
```

No:

```text
LLM SDK
search engine
trading logic
memory system
vector database
planning
Monte Carlo
browser
market feeds
```

Those belong above it.

The QDW constitutional rule survives:

> A state transition is never accepted because software exists or an agent says it succeeded. It is accepted only because the required recorded gates passed.

QDW already formalized the distinction between `PROVEN`, `IMPLEMENTED_UNVERIFIED`, `UNVERIFIED`, `BLOCKED`, and `FAIL`, and requires recorded verification runs and hashed artifacts rather than narrative completion.

---

# 5. Proof levels

Reuse the QDW verification ladder.

A receipt carries:

```text
V0 ... V12
```

rather than merely `PASS`.

Example policy:

```text
update private scratch state       V2
update local derived metric        V4
update canonical economic claim    V7
promote autonomous worker          V8
execute $50 external action        V9
deploy autonomous capital policy   V12
```

Authority can require proof level:

```yaml
grant:
  capability: wallet.trade
  minimum_proof_level: V9
```

So risk determines verification depth.

---

# 6. A-TASK becomes a state-transition request

`atask` should remain tiny.

Its purpose is still:

```text
goal
→ autonomous task
→ externally validated result
→ bounded human decision
→ continue
```

The repo already treats externally validated claims, content-addressed receipts, run cost/time/tokens, and the task DAG as first-class objects.

Under A-COM:

```text
A-TASK = proposed state transition
```

A task cannot complete because an agent says:

> done.

It completes only when:

```text
required gates → PASS
```

---

# 7. A-LOOP becomes purely mechanical

The autonomy loop is:

```text
while goal != VERIFIED:

    read canonical state

    derive READY tasks

    rank available tasks

    acquire necessary grant

    execute worker

    collect receipt

    execute gates

    if PASS:
        commit transition
    else:
        retry / decompose / challenge / escalate
```

The loop contains essentially no intelligence.

Intelligence lives in interchangeable policy modules.

This is desirable.

---

# 8. The recursive layer architecture

The big breakthrough is that **a completed A-COM run is itself valid input to another A-COM procedure**.

So A-COM becomes recursively composable.

```text
ACom(run)
   ↓
ACom(analyse run)
   ↓
ACom(replay run N ways)
   ↓
ACom(search improvements)
   ↓
ACom(test improvements)
   ↓
ACom(promote best)
```

There is no privileged top level.

Every optimization process must itself produce a valid receipt.

---

# 9. A-COM Procedures

Above the kernel, define standardized procedures.

They are like microprocessor instructions implemented as verified programs.

Examples:

```text
SEARCH
REPLAY
MONTE_CARLO
COUNTERFACTUAL
RED_TEAM
TOOL_DISCOVERY
DATA_DISCOVERY
DECOMPOSE
ENSEMBLE
OPTIMIZE
COMPARE
AB_TEST
BACKTEST
FALSIFY
PROMOTE
```

Each procedure defines:

```text
input schema
output schema
budget
determinism requirements
required evidence
acceptance gates
```

---

# 10. Historical run optimizer

This is one of the strongest recursive procedures.

Given a completed run:

```text
R0
```

launch:

```text
Replay(R0, N=1000)
```

Vary:

```text
model
prompt
tool order
retrieval strategy
search depth
context selection
task decomposition
budget
temperature
memory snapshot
candidate evidence
sub-agent count
reasoning style
execution order
```

But keep:

```text
world snapshot
acceptance gate
objective
```

fixed.

Then produce:

```text
R1...R1000
```

and compare through the same hard evaluator.

This gives:

$$
BestKnownPath(T)
=
\arg\max_{R \in Replay(T)}
Utility(R)
$$

subject to gates.

The historical execution graph becomes a permanent laboratory.

---

# 11. Counterfactual mining

Do not merely ask:

> Could the run have been cheaper?

Ask:

```text
What other valid conclusions could the same evidence have supported?
```

Given evidence set `E`:

```text
enumerate candidate claims C1...Cn
```

Then test each claim against:

```text
existing graph
claim schema
required evidence
gate
```

This extracts unused epistemic value from historical work.

One expensive research run might resolve:

```text
original claim: HBM.GAP

plus:
HBM.WTP
HBM.LAG
DRAM.CAPACITY_DISPLACEMENT
AI.SERVER_COST_SENSITIVITY
```

No source gets read only once.

---

# 12. Information Expansion Procedure

This should be standardized.

Call it:

```text
EXPAND_INPUT_SPACE
```

Question:

> Does there exist an additional datasource, API, MCP, dataset, sensor, paid report, human expert or tool that would materially improve the expected quality of this run?

The procedure outputs candidates:

```yaml
candidate_input:
  provider: TrendForce
  object: HBM supply report

  acquisition_cost:
    money: 1.00
    latency_seconds: 20

  expected_effect:
    affected_claims: 8
    unresolved_cruxes: 3
    estimated_information_gain: HIGH
```

Then decide whether acquisition is economically justified.

---

# 13. Value of Information

You cannot perfectly calculate information value.

You do not need to.

Use an explicit approximate policy.

$$
VOI =
P(\text{changes decision})
\times
DecisionValue
\times
ExpectedReliability
\times
DownstreamReuse
$$

Then:

$$
Acquire
\iff
VOI > AcquisitionCost \times SafetyFactor
$$

The variables can be rough buckets.

Example:

```text
P_changes_decision: 0.35
decision_value: $1000
source_reliability: 0.9
reuse_factor: 3

VOI ≈ 945
```

A $1 report is obviously worth acquiring.

No need for fake precision.

---

# 14. Deterministic acquisition policy

The agent should not arbitrarily decide to buy every dataset.

Define rules:

```yaml
acquire:
  if:
    - target_claim is UNKNOWN or DISPUTED
    - source accepted by evidence contract
    - expected evidence uniqueness >= MEDIUM
    - estimated_VOI / cost >= 5

reject:
  if:
    - duplicate of existing evidence
    - stale relative to current source
    - cannot alter any unresolved claim
    - rights prohibit intended use
```

The LLM may estimate the inputs.

The final acquisition decision is policy code.

---

# 15. Common sense remains valid — but typed

Some things cannot become mathematical truth.

Fine.

Represent:

```yaml
estimate:
  type: heuristic
  evaluator: agent
  value: HIGH
  rationale_hash: ...
```

Do not pretend it is formal proof.

Then gates may explicitly allow:

```text
2 deterministic predicates
+
1 heuristic predicate
```

with appropriate proof level.

This preserves epistemic honesty.

Sanskritree already converged on the necessity of distinguishing formally proved claims from `OUTSIDE_FORMAL` and genuinely unsupported claims instead of pretending everything is theorem-provable.

---

# 16. MWGYM becomes the procedure/world generator

This is where `mwgym` becomes much more important.

Its role should become:

> **Generate replayable worlds in which A-COM procedures can be evaluated.**

A world defines:

```text
initial state
available evidence
hidden future state
available tools
tool costs
budgets
external constraints
ground-truth outcome
```

Example:

```text
WORLD:
Etsy / Sep 2024

Agent sees:
all information available Sep 1

Task:
allocate £500

Then world reveals:
Q4 outcome
```

Same idea for:

```text
HBM shortage 2024
container shipping 2020
uranium 2003
palladium 2000
NIL Sep 2026
ZEC/XMR Aug 2026
```

Now we can test whether a procedure would actually have identified historical trades before the move.

---

# 17. MWGYM as an engine generator

Go one level further.

Instead of merely generating worlds:

```text
mwgym generates A-COM procedure challenges
```

Example:

```text
Can an agent identify the bottleneck?
Can it construct the 5 canonical predicates?
Can it detect the kill condition early?
Can it avoid buying unnecessary information?
```

Then procedure variants compete.

Example:

```text
KillfeedDetector_v1
KillfeedDetector_v2
KillfeedDetector_v3
```

CG evaluates them over 100 historical worlds.

The best gets promoted.

---

# 18. CG becomes the CPU benchmark lab

CG already gives:

```text
deterministic worlds
replay
content-addressed RunReceipts
Merkle event roots
quality gates
statistical comparison
```

Its run ID is derived from the worldpack, scenario, candidate, seed and Merkle root of run events.

So CG becomes:

> **the place where A-COM procedure implementations earn promotion.**

A procedure cannot become canonical because it looks clever.

It must outperform the current version in frozen worlds.

---

# 19. Automated optimization hierarchy

This gives us recursive optimization levels.

## L0 — execution

Run task.

## L1 — critique

Find mistakes in the run.

## L2 — replay

Execute variants.

## L3 — search

Explore procedure parameter space.

## L4 — tool expansion

Ask whether new tools/data improve results.

## L5 — architecture mutation

Generate modified procedures.

## L6 — world generation

Generate new adversarial environments.

## L7 — meta-optimization

Evaluate whether the optimization process itself is worth its compute/cost.

Every level is still A-COM.

---

# 20. Economic governor

Infinite computation does not imply infinite external cost.

The system must distinguish:

```text
cheap cognition
expensive calls
paid data
human time
capital risk
external actions
```

Define:

$$
ExpectedNetValue =
ExpectedImprovementValue
-
ComputeCost
-
DataCost
-
LatencyCost
-
RiskCost
$$

A recursive procedure continues while:

$$
MarginalExpectedNetValue > 0
$$

Again, estimates can be approximate.

The important point is that the policy is explicit and logged.

---

# 21. Agent swarm allocation

Do not let 1,000 agents independently research the same thing.

Canonical state produces a gap map.

```text
UNKNOWN claim
stale observation
DISPUTED claim
missing evidence
weak causal edge
failed gate
```

Then rank:

$$
Priority =
\frac{
ExpectedInformationGain
\times
DownstreamDependencyCount
\times
DecisionImpact
}{
ExpectedCost
}
$$

Workers claim gaps atomically.

Duplicate work becomes measurable waste.

---

# 22. Information density objective

Worker performance should not be measured primarily in tokens, prose, or benchmark aesthetics.

Measure:

```text
validated new observations
resolved UNKNOWN claims
successfully falsified claims
verified causal edges
state flips caught
reused evidence
downstream claims improved
```

minus:

```text
duplicates
unsupported claims
stale evidence
unnecessary paid calls
invalid transitions
```

Define:

$$
EpistemicYield =
\frac{VerifiedUsefulStateDelta}{Dollar + Time}
$$

WorkerKit can optimize this.

---

# 23. Killfeed becomes the canonical external-state engine

Killfeed runs continuously against markets and sectors.

Every bottleneck has:

```text
NEED
GAP
LAG
WTP
NOSUB
```

Each is a canonical claim.

Example:

```text
memory.hbm.NEED   TRUE
memory.hbm.GAP    TRUE
memory.hbm.LAG    TRUE
memory.hbm.WTP    TRUE
memory.hbm.NOSUB  TRUE
```

A state flip emits:

```text
CLAIM_FLIPPED
```

Trades subscribe to the graph.

Thus:

```text
claim transitions
→ thesis transitions
→ trade transitions
```

---

# 24. The research feed

Noisy streams exist only to seed exploration.

```text
X
Reddit
earnings transcripts
papers
SEC filings
government releases
specialist reports
order books
shipping feeds
lead-time surveys
GitHub
developer activity
```

The feed itself does not update canonical truth.

Pipeline:

```text
RAW FEED
   ↓
SIGNAL FILTER
   ↓
SEED
   ↓
ENTITY/CLAIM RESOLUTION
   ↓
existing claim?
   ├── yes → challenge/refresh
   └── no  → candidate claim
   ↓
CRUX DETECTOR
   ↓
A-TASK
   ↓
hard-source research
   ↓
evidence
   ↓
gate
   ↓
canonical transition
```

---

# 25. Persistent dossiers

Each entity has an explicit schema.

Examples:

```text
crypto_asset
company
industry
commodity
protocol
technology
regulation
supply_chain_node
market
```

A Zcash researcher does not produce another `zcash-thesis.md`.

It adds to:

```text
ZEC canonical dossier
```

Future agents inherit it.

Research cost therefore falls over time.

---

# 26. Information packets survive from HXRMXS

The HXRMXS Truth Engine already had the right ingestion idea:

```text
source
→ Information Packet JSON
→ claims
→ review
→ ingestion
→ before/after state delta
→ version
```

That should survive almost intact.

Change:

```text
subjective belief weights
```

into:

```text
typed evidence
explicit evidence role
formal/empirical claim state
gate
```

where possible.

---

# 27. Nyah survives as the autonomous maintenance loop

Nyah already implemented:

```text
read completeness
→ identify gaps
→ deterministic tasks
→ prioritize
→ dispatch workers
→ log results
```

plus append-only event logs, canonical digests, immutable schemas, Merkle checkpoints, typed relations and incremental change feeds.

That becomes A-COM's:

```text
GAP SCHEDULER
```

---

# 28. QDW Forge survives as the authority layer

Keep:

```text
Capability
Grant
Invocation
CapabilityProfile
DataRightsHandle
```

Its `CapabilityLease` already represents scoped expiring invocation rights with call/spend limits.

This becomes the base for:

```text
tool credentials
wallet permissions
paid-data permissions
API budgets
deployment rights
human escalation
```

---

# 29. QDW Sandbox survives as the missing-truth market

It already supports:

```text
TASK
DATA
EVIDENCE
ASSET
```

bounties and treats humans as capability providers.

So unresolved canonical state can generate a bounty automatically.

```text
claim UNKNOWN
→ evidence bounty
→ competing submissions
→ deterministic verification
→ reward winner
→ state update
```

---

# 30. WorkerKit becomes the economic execution plane

WorkerKit handles:

```text
real work
external venues
trajectories
payments
outcomes
receipts
```

Every real-world run emits an A-COM receipt.

Its historical execution data feeds:

```text
policy learning
cost prediction
worker selection
model routing
replay optimization
```

---

# 31. Pearl integration

Pearl can eventually attest portions of the cognition plane.

Potential role:

```text
proof that AI computation occurred
```

A-COM still determines:

```text
whether result satisfied the gate
```

So:

```text
Pearl = cognition attestation
CG/WASM = result verification
A-COM = state-transition authority
```

Do not conflate them.

---

# 32. Recursive self-improvement

Every canonical component is versioned:

```text
gate_v17
policy_v8
worker_v32
procedure_v5
worldpack_v11
```

A candidate version cannot replace the current one directly.

It must:

```text
generate candidate
↓
benchmark in CG/MWGYM
↓
run adversarial worlds
↓
compare statistically
↓
pass promotion gate
↓
emit PROMOTE receipt
```

Then:

```text
v17 → v18
```

is itself a canonical A-COM transition.

---

# 33. Hard rule: no prose as terminal output

A report may be generated for humans.

It is never the canonical artifact.

Every run must terminate in one or more of:

```text
observation added
claim resolved
claim challenged
edge added
task completed
gate passed/failed
grant changed
procedure promoted
external outcome recorded
```

Markdown is a view.

State is the product.

---

# 34. Hard rule: no duplicate cognition without reason

Before spawning work:

```text
resolve target against canonical graph
```

If equivalent work exists:

```text
reuse it
```

If stale:

```text
refresh it
```

If disputed:

```text
challenge it
```

If genuinely absent:

```text
create it
```

This is the OpenPāṭala identity-resolution lesson generalized to cognition.

---

# 35. Hard rule: absence is not false

Always distinguish:

```text
FALSE
UNKNOWN
SOURCE_FAILURE
```

QDW explicitly encoded this invariant for sources and economic inputs: database/source failure must not silently become zero results or zero opportunity.

This is protocol-level.

---

# 36. The full stack

```text
                LIVE WORLD
                    │
        feeds / APIs / humans / markets
                    │
                    ▼
              SIGNAL LAYER
                    │
                 seeds
                    ▼
            CANONICAL GRAPH
                    │
              unknown cruxes
                    ▼
             GAP SCHEDULER
                    │
                  TASK
                    ▼
        ┌─────────────────────┐
        │ UNLIMITED COGNITION │
        │ agents / search /   │
        │ tools / simulations │
        └─────────────────────┘
                    │
               proposals
                    ▼
             EVIDENCE LAYER
                    │
                    ▼
        ┌─────────────────────┐
        │     A-COM KERNEL     │
        │ schemas / grants /  │
        │ gates / replay /    │
        │ state transitions   │
        └─────────────────────┘
                    │
           verified transition
                    ▼
             CANONICAL STATE
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
     Killfeed      MW       Atask/ALoop
        │           │           │
        ▼           ▼           ▼
     trading      work       autonomy
                    │
                    ▼
               WorkerKit
                    │
               real outcome
                    │
              RECEIPT
                    │
                    ▼
              CG / MWGYM
                    │
          replay / optimize / mutate
                    │
                    └──────────────► A-COM
```

---

# 37. The recursive optimizer

Every completed run enters:

```text
POST_RUN_PIPELINE
```

Default procedures:

```text
1. VERIFY receipt integrity
2. EXTRACT unused evidence
3. FIND unfilled dependent claims
4. REPLAY obvious alternatives
5. TEST cheaper execution paths
6. SEARCH available tools/data that could have improved result
7. ESTIMATE whether extra information would have justified its cost
8. RED-TEAM result
9. GENERATE candidate procedure improvements
10. BENCHMARK candidates
11. PROMOTE only if hard gate passes
12. PROJECT all useful state deltas back into canonical graph
```

Nothing gets wasted.

---

# 38. Historical replay becomes a permanent asset

Every historical run is a world.

Thus:

```text
history ≠ logs
```

History is:

```text
training environments
counterfactual environments
policy benchmarks
procedure benchmarks
cost benchmarks
causal datasets
```

As compute becomes cheaper, old runs become **more valuable**, because they can be replayed more extensively.

---

# 39. The ultimate objective

A-COM should optimize:

$$
\boxed{
Verified Consequential State Improvement
\over
Cost
}
$$

Not:

```text
tokens
agent turns
beautiful prose
benchmark score
number of tasks
```

The system asks:

> How much verified useful world-state improvement did this cognition produce?

---

# 40. Minimal build order

Do not start with Cartesi, Pearl, ZK, staking or tokens.

### Phase A — hard local kernel

Build:

```text
canonical JSON
hashing
event log
replay
state root
schemas
TransitionReceipt
WASM gate ABI
Grant
```

### Phase B — adapters

Wire:

```text
atask
cg
WorkerKit
Killfeed
```

### Phase C — recursive post-run engine

Implement:

```text
REPLAY
COUNTERFACTUAL
RED_TEAM
TOOL_DISCOVERY
VALUE_OF_INFORMATION
```

### Phase D — MWGYM worlds

Turn historical episodes into replayable environments.

### Phase E — automatic gap allocation

Port Nyah-style:

```text
state → gaps → tasks → workers
```

### Phase F — capability economics

Port QDW Forge grants and QDW Sandbox bounties.

### Phase G — distributed verification

Only then:

```text
independent validators
commit/reveal
Cartesi
Pearl
RISC Zero
Celestia
staking/slashing
```

---

# 41. Constitutional invariants

Freeze these immediately:

1. **Agent output is never canonical state.**
2. **Every canonical transition has a replayable receipt.**
3. **Every consequential action requires an explicit grant.**
4. **Every gate is versioned and content-addressed.**
5. **Rule changes are separate state transitions, never silent edits.**
6. **Missing data is UNKNOWN, never FALSE or zero.**
7. **Evidence and inference are separate objects.**
8. **Prose is never the terminal canonical artifact.**
9. **Historical runs are immutable and replayable.**
10. **A candidate policy cannot promote itself.**
11. **The evaluator must be independent from the generator where practical.**
12. **Every expensive information acquisition must have an explicit purpose and cost record.**
13. **New work must resolve, refresh, challenge or extend canonical state.**
14. **Duplicate work is measured as waste.**
15. **All higher-order optimization remains subject to the same kernel.**

---

# 42. Final mental model

A conventional autonomous agent is:

```text
model
→ think
→ tool
→ act
```

A-COM is:

```text
            unlimited speculative cognition
                        │
                        ▼
               candidate transitions
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      evidence        grants        proofs
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                  HARD KERNEL
                        │
                  PASS / FAIL
                        │
                        ▼
                canonical state
                        │
              recursively replayed
                        │
                        ▼
                 better cognition
```

The recursion never weakens the kernel.

It only increases the number and quality of proposals hitting it.

That is the key architectural property.

As intelligence becomes arbitrarily cheap:

$$
\boxed{
ProposalRate \rightarrow \infty
}
$$

but:

$$
\boxed{
CanonicalStateChange
\text{ remains bounded by hard verification}
}
$$

That is the system.

The next concrete engineering move is to extract the smallest reusable pieces from **QDW, OpenPāṭala, `atask`, CG, Nyah and QDW Forge** into a new `/acom` repo rather than adding this abstraction into any one of those existing projects. The first end-to-end demonstration should be one Killfeed HBM claim and one ordinary `atask`, both producing the **same `TransitionReceipt` type**. If those two very different domains compose against the same kernel, the abstraction is real.
