# Objects — the seven primitives and their rules

Full shapes: `schemas/acom.json`. Constructors: `acom/objects.py`.

- **STATE** — `{cursor, rules_commit, event_root, state_root}`. Never
  stored directly; derived by replaying the store to a cursor.
- **CLAIM** — `{id, statement, domain, result: bool3}`. Id is
  content-derived: same statement + domain = same id, so duplicate
  claims are impossible by construction (invariant 14).
- **EVIDENCE** — `{id: sha256:…, metric, value, unit, as_of, source}`.
  Immutable. Never alters truth alone (invariant 7 needs inference kept
  in CLAIM/apply, not in evidence rows).
- **TASK** — `{id, task_kind, target, acceptance, status}`. READY →
  RUNNING → DONE/FAILED only via receipts, never by assertion.
- **RUN** — `{id, task, worker, model, tokens, cost, duration_ms, …}`.
  Cost/time/tokens are first-class: the economic governor (§20) and
  EpistemicYield (§22) read them, not prose.
- **GATE** — `{id, runtime: wasm, program_hash}`. Registry in
  `acom/gates.py`; new logic = new id (invariant 5). Built-ins:
  `two-sources-v1`, `claim-resolved-v1`, `evidence-fresh-v1`,
  `no-duplicate-v1`.
- **GRANT** — `{subject, capability, constraints, predicates, expiry,
  minimum_proof_level, signature}`. Verified in `acom/grants.py`;
  unsigned = denied, expired = denied, over-limit = denied.
