# QP Processor — mathematical primitive

The processor is **not** another truth primitive.

A QP proof is about acceptance:

\[
\Pi =
Verify(
State,
Proposal,
Evidence,
Authority,
Programs
)
\]

A processor is about bounded speculative computation:

\[
\mathcal P :
(I,S,O,B,C,H)
\longrightarrow
(O',E',A',F,R)
\]

where:

- \(I\) — typed input artifacts;
- \(S\) — current noncanonical working state;
- \(O\) — unresolved QP proof obligations;
- \(B\) — resource budget;
- \(C\) — available technical capabilities;
- \(H\) — verified historical foundations;
- \(O'\) — proposed outputs/sub-obligations;
- \(E'\) — candidate evidence/artifacts;
- \(A'\) — proposed external actions, still requiring grants;
- \(F\) — typed failure/blocker;
- \(R\) — measured run receipt.

A processor may **produce things that help a proof**.

It may never make those things canonical merely by producing them.

## Processor identity

A processor version is content-addressed over:

\[
ProcessorSpec =
(
id,
version,
kind,
I,
O,
handles,
capabilities,
proofOutputs,
resourceModel,
fallback,
mutationSpace,
evaluatorContract,
implementationHash
)
\]

\[
processorRoot = H(ProcessorSpec).
\]

Changing semantics means a new root/version.

## Processor run

A run binds:

\[
ProcessorRun =
(
processorRoot,
ContractRoot,
ProofObligations,
InputsRoot,
WorldRoot,
PolicyRoot,
Budget,
OutputsRoot,
Metrics,
Failures,
ProofRefs
)
\]

This is the unit that Seed0/CG can compare.

## What makes this "microprocessor-like"

A-COM already defines the instruction set:

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

Processors are more like reusable instruction implementations / microcode:

```text
problem.decompose
history.retrieve
reuse.search
web.search
data.discover
tool.discover
code.build
code.test
probe.design
redteam.falsify
repair.propose
cg.simulate
cg.replay
cg.compare
world.generate
trajectory.analyse
seed0.mutate
seed0.tournament
block.resolve
```

The important rule is that the ISA remains small while the processor library can
grow.

## Stuck-proof behavior

When a direct attempt fails, the runtime should not simply "try harder."

It executes a typed fallback pack:

```text
proof.stuck:
  history.retrieve
  reuse.search
  tool.discover
  web.search
  data.discover
  problem.decompose
  cg.simulate
  redteam.falsify
  repair.propose
```

Stop when:
- a new admissible evidence route exists;
- a candidate passes the frozen evaluator;
- a blocker is mechanically certified;
- budget says STOP.

This is the exact place for future new processors. They compete in CG; they do
not enlarge the hard kernel.
