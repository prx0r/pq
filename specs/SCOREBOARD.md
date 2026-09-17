# Scoreboard — is any bundle perfect already?

33 reviews in `reviews/`. Verdict: **No. Nothing is 10/10.** The ceiling is 9/10,
held jointly by the control-plane tip, the complete system, and the validation
labs. Each leader fails a different axis, which is exactly why the unified
system needs all of them.

## Top tier (9/10 — closest, still not perfect)

| Bundle | Score | Why not perfect |
|---|---|---|
| agentcom_control_econ_canonical_v07 | 9.0 | Reference not production. OpsBoard 14/14 + autonomy 8/8 proven, but live money/authority rails stubbed, externals simulated. |
| agentcom-complete-v0.6-final | 9 | Full spec→QP→tournament→product→H-task→autonomy loop, but gated on fake drivers. Real builder/executor not closed. |
| agentcom_validation_lab_v07 | 9 | Best independent verifier (11 checks, finished product, 0–9 autonomy + audit). Verifier is OpsBoard-specific, autonomy constants live elsewhere. |
| agentcom_validation_lab_v06 | 9 | Clean ProofRelay baseline (9 checks, 3 TRUE/2 FALSE, preserved red iteration). Narrow verifier, synthetic Run2. |
| agentcom-spec-to-proof-testing-kernel-2026-09-14 | 9 | Best adversarial engine (driver firewall, 55/55 + 5000 fuzz, 21 banked failures). Single gold spec, sim world. |

## Second tier (8–8.5 — load-bearing parts)

| Bundle | Score | Role in unified system |
|---|---|---|
| agentcom_control_econ_canonical_v06 | 8.5 | First runnable product under frozen roots (T0–T13, ProofRelay 11/11, Run2 reuse). Superseded by v07. |
| agentcom-v5-complete-system-human-ml-autonomy-2026-09-14 | 8.5 | Only executable system (complete_runtime + control_plane + human_surface :9917 + GhostCompute 28/28). Reference-scale, externals stubbed. |
| agentcom-v2-testing-kernel-full | 8.5 | Best JS validation kernel (clean-extract, 4-cycle proof). Simulated cognition. |
| autobuild-v0.2-hardened | 8.5 | Fail-closed entry, PENDING-vs-VERIFIED boundary, honest NOT_PROVEN. Live adapters open. |
| agentcom-human-econ-kernel-v4 | 8.0 | Integrated kernel + T01–T04 trials (QuotaLedger, proof types, Harbor forgery). V3 recipes partly unexecutable, adapters are shims. |
| agentcom-v2-testing-kernel / -final | 8.0 | Honest Python science kernel + strict tournament. Fixture/legacy-selector gaps. |
| agentcom_testing_kernel | 8.0 | Best admission/coverage/atomic-budget hardening. Fixture-gated harness. |
| agentcom-acom-meta-kernel-2026-09-14 | 8.0 | Enforced Proof-vs-Processor split, 5-lane tournament, 137 tests. Authority/execution adapters open. |
| agentcom-validation-v4 | 8.0 | Typed calculus + QuotaLedger hidden-test tournament. Fixture human, fake harbor, no campaign plane. |
| autonomous-economic-discovery-control-plane-v3-2026-09-14 | 8.0 | Best operating model (worlds/scheduler/H-desk, 32/32). No durable runtime. |
| tom-...-v4-openai-harness-2026-09-14 | 8.0 | Only executable discovery path (SQLite/OpenAI/QP-Ed25519/leases, 44/44). HMAC receipts, no session-close. |
| agentcom-v4-human-processors-hloop-harbor-2026-09-14 | 8.0 | Only Proof-vs-Processor formalization + HLoop/Harbor/economics (36/36). Live rails simulated. |

## Middle tier (6.5–7.5 — doctrine + substrate)

| Bundle | Score | Note |
|---|---|---|
| agentcom_control_econ_canonical_v05 | 7.5 | Strongest science/reference kernel of its generation; smokes only, no built product. |
| agentcom-canonical-meta-v0.4.0-final | 7.5 | Solid processor/tournament substrate; superseded by v0.6. |
| agentcom-human-econ-kernel-final | 7.5 | Old-lineage integrated kernel; superseded by v4. |
| qp-frontier-experiment | 7 | Clean proof-vs-processor ABI, RELEASE-as-baseline tournament. Synthetic demo, no H/M/campaign. |
| campaign-control-plane-2026-09-14 | 6 | v1 base, green but live self-attestation trust bug (fixed in scarce-state v2). Fixtures only. |
| scarce-state-control-plane-v2-2026-09-14 | 7 | Fixes the trust bug (18/18). File-state only. |
| meta_seesaw_agentcom_2026-09-15 | 7 | Honest PROPOSED-only allocator; unwired patches. |
| seesaw-agent-module-v0.1 | 7 | Crisp strategy primitive + event loop; uncalibrated, no settlement. |
| autobuild-v0.1 | 7 | Deterministic compiler core; superseded by hardened. |
| agentcom_human_econ_runtime | 7 | v0.4.0 SDK successor (67/67 + 8/8 dogfood). No mission loop. |
| agentcom-meta-kernel-final | 6.5 | Clean core subset, correctly scoped, smaller than human-econ. |

## Lower tier (packaging / thin slices)

| Bundle | Score | Note |
|---|---|---|
| agentcom_meta_canonical | 6 | v0.3.1 SDK/distribution. Best processor-science doc, no live runtime. |
| agentcom_v06_release_bundle | 6 | 4-file envelope; perfect for what it is, reuse the pattern. |
| agentcom_v07_release_bundle | 5.5 | Same envelope, SHA256SUMS uses absolute /mnt/data paths — fix to bare filenames. |
| agent-plugin-factory-v0.1 | 5.5 | Runnable scoring→packet slice; eval/host half is design-doc. |

## Why nothing is perfect

Each 9/10 fails a different axis: v07 lacks production rails, complete-v0.6
lacks a real executor, validation labs lack generality, spec kernel lacks a
second gold spec. The 8–8.5 tier holds the missing pieces (executable runtime,
hardened builder, proof/processor formalization, discovery harness), and the
middle tier holds the doctrine. The unified build must therefore integrate —
not crown — a winner.
