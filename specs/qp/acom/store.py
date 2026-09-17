"""Append-only event store with replay and Merkle roots (northstar §4).

State is ALWAYS replayable from the event log. The store holds no
intelligence: append bytes, recompute roots, replay folds. Readers
derive STATE cursors; writers never edit history.
"""

import json
import os

from .canonical import merkle_root, sha256_hex


class Store:
    """One JSONL file. Each line: {seq, type, payload, prev, hash}."""

    def __init__(self, path: str):
        self.path = path
        self._hashes = []
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._hashes.append(json.loads(line)["hash"])

    def append(self, etype: str, payload: dict) -> dict:
        """Append one event; returns the chained entry (seq, hash)."""
        prev = self._hashes[-1] if self._hashes else sha256_hex(b"genesis")
        entry = {"seq": len(self._hashes), "type": etype,
                 "payload": payload, "prev": prev}
        entry["hash"] = sha256_hex(
            (prev + etype).encode() + json.dumps(
                payload, sort_keys=True, separators=(",", ":")).encode())
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        self._hashes.append(entry["hash"])
        return entry

    @property
    def event_root(self) -> str:
        """Merkle root over all entry hashes (empty store hashes empty)."""
        return merkle_root(self._hashes)

    @property
    def cursor(self) -> int:
        """Replay position: count of appended entries."""
        return len(self._hashes)

    def verify_chain(self) -> bool:
        """Recompute every link. False on ANY tampering. No exceptions."""
        try:
            prev = sha256_hex(b"genesis")
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    e = json.loads(line)
                    want = sha256_hex(
                        (prev + e["type"]).encode() + json.dumps(
                            e["payload"], sort_keys=True,
                            separators=(",", ":")).encode())
                    if e["hash"] != want or e["prev"] != prev:
                        return False
                    prev = e["hash"]
            return True
        except Exception:
            return False

    def replay(self, fold, initial):
        """Fold every payload in order: state = fold(state, type, payload)."""
        acc = initial
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    e = json.loads(line)
                    acc = fold(acc, e["type"], e["payload"])
        return acc
