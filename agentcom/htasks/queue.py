"""H-tasks — human work queue with leases and safe-default expiry.

Lifecycle: emitted → displayed → acknowledged → answered → expired.
Expiry is never approval: the task's safe_default applies instead.
Secrets never enter this queue (see vault rule in docs/HTASK_PANEL.md).
Provenance: schemas from scarce-state htask drafts; lifecycle is qpbot-new.
"""
from __future__ import annotations

import hashlib
import json
import os
import time


def _hid(task_id: str, question: str) -> str:
    return hashlib.sha256(f"{task_id}:{question}".encode()).hexdigest()[:16]


class HTask:
    Kinds = ("digit", "confirm", "secret")

    def __init__(self, task_id: str, kind: str, question: str,
                 prediction: str = "", confidence: float = 0.0,
                 lease_s: int = 300, safe_default: str = "deny",
                 campaign: str = "", lane: str = ""):
        if kind not in self.Kinds:
            raise ValueError(f"unknown kind {kind}")
        self.task_id = task_id
        self.kind = kind
        self.question = question
        self.prediction = prediction
        self.confidence = confidence
        self.safe_default = safe_default
        self.campaign = campaign
        self.lane = lane
        self.state = "emitted"
        self.created = int(time.time())
        self.deadline = self.created + lease_s
        self.context_hash = _hid(task_id, question)
        self.answer = None

    def display(self):
        self._require("emitted")
        self.state = "displayed"
        return self.view()

    def acknowledge(self):
        self._require("displayed")
        self.state = "acknowledged"

    def answer_task(self, answer: str, prediction_before_display: str = ""):
        self._require("acknowledged", "displayed")
        if self.kind == "secret":
            raise ValueError("secrets deposit to the vault, never the queue")
        self.answer = {"value": answer,
                       "prediction_before_display": prediction_before_display,
                       "ts": int(time.time())}
        self.state = "answered"
        return self.answer

    def expire(self, now: int = 0):
        if self.state in ("answered", "expired"):
            return self.state
        if (now or int(time.time())) >= self.deadline:
            self.state = "expired"
            self.answer = {"value": self.safe_default, "expired": True,
                           "ts": int(time.time())}
        return self.state

    def view(self) -> dict:
        return {"task_id": self.task_id, "kind": self.kind,
                "question": self.question, "prediction": self.prediction,
                "confidence": self.confidence, "state": self.state,
                "context_hash": self.context_hash,
                "campaign": self.campaign, "lane": self.lane,
                "deadline": self.deadline}

    def to_record(self) -> dict:
        """Full persisted form: view + answer + private timing fields."""
        return (self.view() | {"answer": self.answer,
                               "created": self.created,
                               "safe_default": self.safe_default})

    @classmethod
    def from_record(cls, raw: dict) -> "HTask":
        """Rebuild from a persisted record. Tolerates the old seed shape."""
        t = cls(raw["task_id"], raw.get("kind", "digit"),
                raw.get("question", ""),
                prediction=raw.get("prediction", ""),
                confidence=raw.get("confidence", 0.0),
                lease_s=300,
                safe_default=raw.get("safe_default", "deny"),
                campaign=raw.get("campaign", ""), lane=raw.get("lane", ""))
        t.state = raw.get("state", "emitted")
        t.created = raw.get("created", t.created)
        t.deadline = raw.get("deadline", t.deadline)
        if raw.get("context_hash"):
            t.context_hash = raw["context_hash"]
        t.answer = raw.get("answer")
        return t

    def _require(self, *states):
        if self.state not in states:
            raise ValueError(f"task {self.task_id} is {self.state}, "
                             f"need one of {states}")


class HQueue:
    """Human queue. In-memory working set + atomic file persist (save/load).
    The dashboard and the daemon share one file; every load sweeps expiries
    so safe-defaults apply even if nobody is watching."""

    def __init__(self):
        self.tasks: dict[str, HTask] = {}

    def emit(self, task: HTask) -> HTask:
        self.tasks[task.task_id] = task
        return task

    def sweep(self, now: int = 0) -> list[str]:
        expired = []
        for t in self.tasks.values():
            before = t.state
            t.expire(now)
            if before != "expired" and t.state == "expired":
                expired.append(t.task_id)
        return expired

    def active(self) -> HTask | None:
        for t in self.tasks.values():
            if t.state in ("displayed", "acknowledged"):
                return t
        return None

    def pending_count(self) -> int:
        return sum(1 for t in self.tasks.values()
                   if t.state in ("emitted", "displayed", "acknowledged"))

    def to_json(self) -> str:
        return json.dumps([t.view() for t in self.tasks.values()], indent=1)

    def records(self) -> list[dict]:
        return [t.to_record() for t in self.tasks.values()]

    def save(self, path: str):
        """Atomic persist: tmp file + rename, so readers never see halves."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.records(), f, indent=1)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "HQueue":
        """Load persisted records; sweeps expiries. Missing file = empty."""
        q = cls()
        if os.path.exists(path):
            for raw in json.load(open(path)):
                try:
                    t = HTask.from_record(raw)
                except (ValueError, KeyError):
                    continue
                q.tasks[t.task_id] = t
        q.sweep()
        return q
