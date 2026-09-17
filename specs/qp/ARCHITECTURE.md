# Architecture — what lives where

`northstar.md` is the thesis. This file is the map. Code: `acom/`.

| Layer | Files | Knows |
|---|---|---|
| Canonical bytes | `acom/canonical.py` | JSON, sha256, Merkle. Nothing else. |
| Objects | `acom/objects.py`, `schemas/acom.json` | 7 shapes + bool3. Validation only. |
| Events | `acom/store.py` | append, chain-verify, replay, roots. |
| Gates | `acom/gates.py` | registry + pure predicates + 4 built-ins. |
| Grants | `acom/grants.py` | expiry, constraints, predicates, fail-closed. |
| Receipts | `acom/receipts.py` | transition(), verify, settle. Sole state path. |
| CLI | `acom/cli.py` | init/demo/verify/chain. No semantics. |
| Demos | `examples/hbm_demo.py`, `examples/atask_demo.py` | two domains, one receipt type. |
| Tests | `tests/test_kernel.py` | 12 checks, every invariant cheaply testable. |

Data flow is one direction: cognition proposes → evidence attaches →
gates execute → receipt settles → store appends → state replays.
Nothing flows backwards. The kernel never calls outward.
