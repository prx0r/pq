# INSANE — things the normal reviews missed

Three hunter passes over all 33 bundles. Everything below is file-verified.
Paths are under `_source/` unless stated.

## Do-not-run-without-reading (security)

- Test Ed25519 key ships in tree and mints valid-format grants:
  `agentcom_control_econ_v07/src/agentcom_meta/wallet.py` (`ExactQPTestSigner`,
  `LocalTestSigner` SHA256-fakes signatures). Any code path that accepts
  these signers is an attestation bypass.
- Runtime self-mints owner authority: `complete-v0.6/src/runtime/full-circle.js`
  auto-creates `HumanSigner` when no identity passed, and `resolveHumanForTest()`
  forges `HUMAN_TEST_FIXTURE` decisions. With `autoHuman:true` any H-task
  closes with no human. Release PROVEN leans on this fixture.
- Phone-reachable auto-actor with zero auth: `control_v07/.../workbench_server.py`
  (`present_or_auto` returns AUTO_LOCAL, `/api/*` no auth, `0.0.0.0` allowed)
  and `WORKBENCH.md` documents phone access while admitting no TLS. The v5
  human surface (`:9917`) and v4 dispatch server (`:8787` `/api/dispatch`)
  are the same shape: real HTTP APIs where one flag flip spends money or
  approves work.
- Arbitrary-command harnesses everywhere: five-lane runner (`copytree/rmtree`
  + `subprocess.run` with task JSON), external/reference drivers (`rmSync` +
  `cpSync`, `spawnSync` on product code, dynamic import traversal test),
  MissionRunner `ProductWorkspace.run_commands`. Sandbox before running any
  lane on untrusted content.
- Live rails present: OpenAI-compatible drivers POST bearer keys
  (`control_v07/.../driver.py`, spec-kernel `drivers.py`, v4-harness
  `openai_agents.py` against `POST /v1/agents/sessions`), Harbor adapter
  shells `harbor run`, GitHub pollers read `GITHUB_TOKEN` and loop uncapped.
  Cost control is flag-based (`--execute`), prompt-guard text is not
  enforcement.
- Dangerous artifacts ship in tree: GhostCompute `app.py /v1/demo-settle`
  marks any quote settled (contradicts its own merchant-readback spec);
  validation-v4 T04 writes an executable `bin/harbor` containing forged
  `QP PASS` stdout; meta-kernel ships `lab_runs/meta_redteam/evil.zip` with
  poison fixtures; lab_v07 challenge template is a backdoor factory
  (`LEAK_SECRET/SAME_CHANNEL/BYPASS_CAPS/BROKEN_AUDIT`). Treat as live
  ordnance, not clean fixtures.
- Real state ships: GhostCompute `ghostcompute.db` (quotes/entitlements),
  v4-harness `control_plane.db` (runs/receipts/leases/grants), validation-v4
  `wallet.sqlite/authority.sqlite/hloop.sqlite` plus a plaintext fixture
  credential on disk (0600, passes only because log check looks at raw
  output). Deleting a db resets that bundle's truth; rerunning demos reuses
  prior state.
- Human-surface server hardcodes wallet pockets, owner-2FA seed, and a
  `github.pr.merge` grant request at import. Running it exposes balances
  instantly.

## Self-certification holes (all real, most already documented as history)

- Campaign v1: one `source:live ok:true` JSONL line promotes to PROVEN with
  no attestation (`validators.py`, proven by its own `test_live_can_prove`).
  Fixed in scarce-v2 via HMAC attestation key — but tests self-sign with the
  same key, teaching the attack pattern. Production needs an external attestor.
- Autobuild-hardened: plan author writes its own judge (`validator_codegen`
  embeds agent `validator_spec`, `bridges` passes targets through verbatim),
  missing requirement fields auto-fill to HARD/PASS, and the strict promotion
  gate (`minimum_uses 3, 90% pass, 0 regressions`) exists as dead code nothing
  calls. Green `VALIDATION.json` is deterministic-core only.
- Validation-v4 quota trial: hidden judge and candidate materialize from the
  same source file; tournament variant order scripts the winner. Frontier
  mock runtime hill-climbs synthetic arithmetic (`capability >= difficulty +
  .35*ambiguity`) and its live adapter can never succeed by design — winners
  stay `IMPLEMENTED_UNVERIFIED` by construction.
- Campaign reward floors (`max(0.9, ...)`) make ranking near-constant; v3
  accepts free-text receipt refs as outcomes; plugin-factory self-scores
  `81.4 PLUGINIZE` from its own candidate file with templated evals that
  cannot fail on real routing.
- Checksum hygiene: manifests hash `__pycache__/*.pyc` (break on Python
  upgrade), v07 release SHA file uses absolute `/mnt/data` paths
  (`sha256sum -c` fails unedited), 147 nested zips-in-zips hide full history
  including duplicated qp-science and lineage snapshots.

## Buried alpha (the actual treasure)

- Money rails are real code, not docs: HMAC one-shot `BudgetWallet`
  (reserve/reconcile, no negatives, replay protection), grant-gated
  `WalletLedger` (fail-closed reserve, idempotent, SQLite WAL), integer-minor
  `QuotaLedger` with 10-thread overspend hidden tests. UI approval stays
  `APPROVED_PENDING_QP` — the production signer is still the missing seam.
- 0-9 human learning exists in three independent implementations with the
  same enforcement (prediction banked before the human sees the task,
  post-hoc scoring impossible): control_v07 `HumanDecisionLearner` (8-gram
  macros, 0600 persist), complete-v0.6 `KeypadPredictor` (softmax online
  learner), v5 `HLoopPolicyModel` (256-dim feature-hash SGD) plus a sequence
  learner reusing the same model. Autonomy ladders escalate on measured
  calibration (presses/Brier/ECE/OOD) with hard blocks on secrets, identity,
  physical, and authorization — and v07 results log a real traverse
  (SHADOW to AUTO at 70 presses, demotion after failures).
- Compute-routing math is a prediction market: `LiveLLMAdapter` with
  geometric-retry expected-cost-to-verified-completion plus UCB model
  ranking, and `GoalAwareBudget` emitting exploit/explore caps that require
  spend grants. Network-read processors (livellm/oracle/company-graph/search)
  feed it by design.
- Harbor trial shape is exact and frozen: instruction plus Dockerfile plus
  `test.sh` to `/logs/verifier/reward.json` plus `task.toml` schema 1.4,
  with processor/contract roots baked into the instruction. Import path
  forces `qp_valid=False` — Harbor reward stays evidence, never authority.
- The seesaw example portfolio is real operational data: 8 projects with the
  ranking, asset-slot picks, and the attention split (Etsy/UKGraph/infra
  percentages, infra capped at support despite scoring highest). The scoring
  weights and deadline/window/unlock formulas are all in tree, uncalibrated.
- The v07 challenge spec is a full control-econ spec disguised as a tiny
  OpsBoard task (0-9 predict-before-display, never-auto classes, QP-bound
  authority, SENT_UNVERIFIED plus independent readback, audit chain,
  tournament, Run-2 reuse). Its mutations corpus (6 backdoor classes, all
  caught with reasons) is a high-value regression set, as is the spec-kernel
  failure bank (21) plus mutation/planner-attack suites plus 5000-fuzz soak
  (note: soak script is an endless CPU burner, `while true` seed +104729).
- GhostCompute fixtures include a recorded LLM oracle plus gold obligations
  plus a 55-row green catalog, enabling offline replay of the live-money
  mission. External lineage is pinned (`external_repos.lock.json`, UPSTREAM
  locks: qp, qdw, livellm, openai-agents, harbor commits).
- QP crypto worth keeping: vendored Ed25519 authority
  (`generateAuthority/signCanonical/verifyCanonical/finalizeGrant`) and the
  v4-harness `evaluate_task` deny-without-signed-grant path with 64-hex
  pubkey-subject plus V0–V12 proof levels. These are the seam-1 fix pieces.
- Quiet seams: WASM declared as verifier ABI with native Python predicates
  behind the identical call contract (zero-toolchain runner opening);
  `verified_import` firewall correct (everything lands UNVERIFIED without a
  QP receipt); learning logs reject secret keys by design; `qp_valid` stays
  false across Harbor imports.

## Contradictions to keep pinned

- Validation reports say harbor/OpenAI not installed and nothing mislabeled
  green, while the same tree implements live `harbor run` and session create.
  Both true: capability present, live run not executed (no keys). Do not read
  either half alone.
- GhostCompute summaries claim 28/28 TRUE including deploy/domain/merge while
  its README states external XMR/DNS/GitHub consequences live in separate
  adapters. Product PASS is real; production-consequence proof is not.
- AGENTS.md forbids arbitrary execution from manifests while reference and
  external drivers execute arbitrary commands and product code. The guardrail
  is aspirational; the code is the truth.
