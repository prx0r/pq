"""A-COM kernel package. Tiny and hard by design (northstar §4).

Knows only: serialization, hashing, IDs, events, replay, roots,
schemas, gates, grants, receipts, transitions. Everything else
(search, models, trading, planning) lives ABOVE as procedures.
"""

from .canonical import PROTOCOL  # noqa: F401
