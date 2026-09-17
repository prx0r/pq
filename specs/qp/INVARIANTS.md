# Invariants — the 15 frozen rules and where each is enforced

From northstar §41. A rule without an enforcement site is a wish.

1. Agent output is never canonical state — `receipts.transition()`
   requires all-PASS; cognition only fills `proposal`.
2. Every transition has a replayable receipt — `store.append("transition")`
   in both demos; `chain` verifies the log.
3. Consequential action needs a grant — `grants.verify_grant()`; proposals
   carry `grant` (null = no external consequence).
4. Gates versioned + content-addressed — `gates.program_hash` from source;
   registry lookup by id; unknown id = FAIL.
5. Rule changes are transitions, not edits — new logic registers a new id;
   old receipts settle against old ids forever.
6. Missing data is UNKNOWN — `claim-resolved-v1` passes only TRUE/FALSE;
   absence can never satisfy it.
7. Evidence and inference separate — evidence rows carry no verdict;
   verdicts live in CLAIM.result via `apply()`.
8. Prose never terminal — receipts contain no free text fields; demos emit
   JSON artifacts, stdout summaries are views.
9. Runs immutable + replayable — store is append-only; `verify_chain()`
   detects any edit (tested with an injected evil line).
10. No self-promotion — no PROMOTE path exists yet by design (Phase C);
    when added it settles through CG worlds, not self-assertion.
11. Evaluator independent from generator — `settle()` re-executes gates
    from bytes; tests assert tampered receipts fail.
12. Expensive acquisition logged — RUN carries cost/tokens/duration;
    VOI policy is Phase C procedure work, schema-ready.
13. New work resolves/refreshes/challenges/extends — TASK.target +
    claim-id stability make duplicates addressable (see 14).
14. Duplicates measured as waste — content-derived claim ids +
    `no-duplicate-v1` gate.
15. Higher-order optimization obeys the kernel — POST_RUN_PIPELINE is
    future work; its outputs must be receipts or they do not exist.
