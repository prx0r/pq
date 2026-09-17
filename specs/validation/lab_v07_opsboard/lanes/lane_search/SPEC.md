# OpsBoard — finished-product challenge

Build a small mobile-friendly operations board for a one-person business.

- The product MUST persist leads, jobs, settings, and audit events in SQLite and MUST survive a process restart.
- CSV import MUST accept `email,name` and MUST deduplicate leads by normalized email without creating duplicates on repeated import.
- The API MUST support creating a job idempotently with a client idempotency key and MUST return the same job for a repeated key.
- The product MUST provide a mobile dashboard showing lead count, pending jobs, delivered jobs, spend used, and the current default view.
- The user MUST be able to choose a low-risk default-view PREFERENCE through the 0–9 human-control system.
- The system MUST predict the human 0–9 choice before displaying each human task and MUST learn from every press after the real outcome is joined.
- Increasingly familiar low-risk PREFERENCE decisions MUST become eligible for local autonomy only after calibrated verified evidence.
- SECRET, IDENTITY, PHYSICAL, and consequential AUTHORIZATION tasks MUST always require real human input even if the system predicts the answer perfectly.
- Provider credentials MUST enter only through a SECRET human task and MUST NOT be persisted in the product database, audit log, dashboard state, or ordinary trajectory logs.
- Creating an external provider account or completing KYC MUST be represented as an IDENTITY human task and MUST NOT auto-resolve.
- Dispatching a job MUST require QP-bound authority for the exact action before any external effect.
- A campaign MUST send AT MOST 3 messages and MUST spend AT MOST 0.50 USD in total, including across restart boundaries.
- Immediately after dispatch the local job MUST be `SENT_UNVERIFIED` and MUST NOT claim delivery from the same dispatch response.
- Delivery MUST become `DELIVERED` only after an independent provider-side readback finds the message.
- Every local state-changing operation MUST append a SHA-256 chained audit event whose chain MUST verify after restart.
- Five implementation lanes MUST use the same ContractRoot and ProofRoot; invalid lanes MUST be rejected before cost ranking.
- Run 2 MUST reuse a Run-1 artifact only when the artifact has a verified proof receipt and MUST keep the same ContractRoot and ProofRoot.
- FINAL ACCEPTANCE MUST produce a runnable finished product, an independent verification report, a QP receipt for the consequential action, the five-lane tournament, human-learning metrics, and a complete test journal.
