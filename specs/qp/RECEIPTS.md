# Receipts — the one artifact

Shape: `schemas/acom.json` → `definitions.receipt`. Built only by
`receipts.transition()`, checked by `verify_receipt()` (id recompute),
settled by `settle()` (id + every gate re-executed from bytes).

Lifecycle: `proposal + evidence + gates → receipt(passed?) → store →
replay → STATE`. FAIL receipts are stored too — a recorded FAIL is
evidence for the next attempt, not garbage.

`proof_level` V0–V12 travels on every receipt; authority maps
capability → minimum level (`GRANT.minimum_proof_level`). Policy table
(V2 scratch … V12 capital policy) lives in northstar §5.

Signatures: the `signature` field is carried and covered by nothing
until the authority layer signs; the kernel never forges one, and
`verify_grant` fails closed on unsigned grants.
