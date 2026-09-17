"""Daemon — job queue with writer exclusivity and UNKNOWN-on-crash.

One writer per session: attach() refuses a second live writer for the same
session id (pi-acp constraint). A job whose worker dies without a verdict
is UNKNOWN with evidence preserved, never FAILED.

The journal persists to disk (JSONL). On boot, any job left `running` by a
dead process is resumed as UNKNOWN with its evidence preserved — crashes
are UNKNOWN, never FAILED, across restarts too.
"""
from __future__ import annotations

import json
import os
import time
import traceback


class SessionRegistry:
    def __init__(self):
        self.writers: dict[str, str] = {}

    def attach(self, session_id: str, worker_id: str):
        if session_id in self.writers:
            raise ValueError(f"session {session_id} already has a writer: "
                             f"{self.writers[session_id]}")
        self.writers[session_id] = worker_id

    def detach(self, session_id: str):
        self.writers.pop(session_id, None)


class Daemon:
    def __init__(self, journal_path: str = ""):
        self.queue: list[dict] = []
        self.registry = SessionRegistry()
        self.journal: list[dict] = []
        self.journal_path = journal_path
        self._next = 1
        if journal_path and os.path.exists(journal_path):
            self._resume()

    def _append_journal(self, entry: dict):
        self.journal.append(entry)
        if self.journal_path:
            os.makedirs(os.path.dirname(self.journal_path) or ".",
                        exist_ok=True)
            with open(self.journal_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _resume(self):
        """Rebuild state from the journal; orphan `running` jobs → UNKNOWN."""
        with open(self.journal_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.journal.append(json.loads(line))
                except ValueError:
                    continue
        by_id: dict[str, dict] = {}
        for e in self.journal:
            if e.get("job_id"):
                by_id[e["job_id"]] = e
                try:
                    n = int(str(e["job_id"]).split("-")[-1])
                    self._next = max(self._next, n + 1)
                except ValueError:
                    pass
        for job_id, e in by_id.items():
            state = e.get("state")
            if state == "queued":
                self.queue.append({"job_id": job_id, "state": "queued",
                                   **{k: v for k, v in e.items()
                                      if k not in ("job_id", "state", "ts")}})
            elif state == "running":
                note = {"job_id": job_id, "state": "UNKNOWN", "resumed": True,
                        "error": "orphaned by dead process; evidence kept",
                        "ts": int(time.time())}
                self._append_journal(note)

    def submit(self, job: dict) -> dict:
        job = {"job_id": f"job-{self._next}", "state": "queued", **job}
        self._next += 1
        self.queue.append(job)
        self._append_journal({"job_id": job["job_id"], "state": "queued",
                              "kind": job.get("kind", ""),
                              "ts": int(time.time())})
        return job

    def tick(self, runner=None) -> dict | None:
        """Run the next queued job once. runner(job) executes it."""
        job = next((j for j in self.queue if j["state"] == "queued"), None)
        if job is None:
            return None
        job["state"] = "running"
        self._append_journal({"job_id": job["job_id"], "state": "running",
                              "ts": int(time.time())})
        try:
            result = runner(job) if runner else {"ok": True}
            job["state"] = "done"
            job["result"] = result
        except Exception as e:  # noqa: BLE001 — crash must bank, not raise
            job["state"] = "UNKNOWN"
            job["error"] = f"{type(e).__name__}: {e}"
            job["trace"] = traceback.format_exc(limit=3)
        self._append_journal({"job_id": job["job_id"], "state": job["state"],
                              "ts": int(time.time())})
        return job
