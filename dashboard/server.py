"""Dashboard — chat left, H-task rail right. Stdlib only.

Token gate: every request needs ?token=<DASH_TOKEN> (env or generated at
boot, printed once to stdout). Binds loopback; the outside world arrives
only through the Cloudflare tunnel.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TOKEN = os.environ.get("DASH_TOKEN", secrets.token_urlsafe(24))
RUNS = os.path.join(ROOT, "runs")
HFILE = os.path.join(RUNS, "htasks.json")
PFILE = os.path.join(RUNS, "provider.json")
DFILE = os.path.join(RUNS, "decisions.jsonl")
SFILE = os.path.join(RUNS, "spend.jsonl")
CFILE = os.path.join(RUNS, "spend_caps.json")
HISTORY: list[dict] = []


def _seed_queue():
    from agentcom.htasks.queue import HQueue, HTask
    q = HQueue()
    q.emit(HTask("demo-digit-1", "digit",
                 "Demo pack finished 3/3. Which lane should lead next?",
                 prediction="7", confidence=0.72, lease_s=3600,
                 campaign="demo", lane="creds-first"))
    q.emit(HTask("demo-approval-1", "confirm",
                 "Approve running the live Pi red-team lane? (no spend yet)",
                 lease_s=3600, campaign="demo", lane="pi"))
    q.save(HFILE)
    return q


def _load_queue():
    """Canonical queue from disk. Sweeps expiries; seeds on first boot."""
    from agentcom.htasks.queue import HQueue
    if not os.path.exists(HFILE):
        return _seed_queue()
    return HQueue.load(HFILE)


def _save_queue(q):
    q.save(HFILE)


def _task_list(q) -> list[dict]:
    return [t.view() | {"answer": t.answer} for t in q.tasks.values()]


def _provider() -> dict:
    if os.path.exists(PFILE):
        return json.load(open(PFILE))
    return {"base_url": "https://opencode.ai/zen/go/v1",
            "model": "muse-spark-1.3-contributor"}


def _responses_text(resp: dict) -> str:
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    return "".join(parts) if parts else resp.get("output_text", "")


def _chat_via_provider(message: str) -> str:
    from agentcom.vault.store import Vault
    prov = _provider()
    if not prov.get("model"):
        return ("No model configured. Set provider + model below, then "
                "deposit your key in the rail — chat goes live after that.")
    v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    usable = [a for a in v.find(kind="llm-inference", tier="paid")]
    if not usable:
        return ("No key in the vault yet. Paste it into the rail's secret "
                "box (it never touches chat) and try again.")
    key = key_name = None
    for cand in usable:
        try:
            key = v.resolve(cand["name"], "dashboard-chat", "chat-session",
                            cand["capability"])
            key_name = cand["name"]
            break
        except ValueError:
            continue
    if key is None:
        return ("Vault keys are present but all spent or expired. "
                "Deposit a fresh key in the rail and try again.")
    model = prov["model"]
    base = prov["base_url"].rstrip("/")
    if model.startswith("muse-spark"):
        # OpenCode Go serves muse-spark via Responses API, not chat/completions.
        req_body = json.dumps({
            "model": model,
            "input": [
                {"role": "system",
                 "content": "You are the pq conversational assistant. "
                            "Autonomous red-team work runs beside this chat; "
                            "answer directly and briefly."},
                *HISTORY[-10:],
                {"role": "user", "content": message},
            ],
            "stream": False,
        }).encode()
        url = base + "/responses"
    else:
        req_body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system",
                 "content": "You are the pq conversational assistant. "
                            "Autonomous red-team work runs beside this chat; "
                            "answer directly and briefly."},
                *HISTORY[-10:],
                {"role": "user", "content": message},
            ],
        }).encode()
        url = base + "/chat/completions"
    req = urllib.request.Request(
        url, data=req_body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.load(r)
        if model.startswith("muse-spark"):
            text = _responses_text(body)
        else:
            text = body["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001 — provider errors surface as chat
        return f"Provider call failed: {type(e).__name__}: {e}"
    HISTORY.append({"role": "user", "content": message})
    HISTORY.append({"role": "assistant", "content": text})
    return text


class Handler(BaseHTTPRequestHandler):
    server_version = "qpbot-dash/0.1"

    def _gate(self) -> bool:
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] != TOKEN:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"bad token")
            return False
        return True

    def _json(self, obj, code: int = 200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        if not self._gate():
            return
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            page = open(os.path.join(ROOT, "dashboard", "static",
                                     "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
        elif path == "/api/tasks":
            # Serving a task IS displaying it to the human: emitted tasks
            # move to displayed so the phone sees live interrupts.
            q = _load_queue()
            touched = False
            for t in q.tasks.values():
                if t.state == "emitted":
                    t.display()
                    touched = True
            if touched or q.sweep():
                _save_queue(q)
            self._json(_task_list(q))
        elif path == "/api/tiles":
            from agentcom.interfaces.agentdeck_bridge import (
                agentdeck_state, tiles_for_status)
            from agentcom.ledger.spend import SpendLedger
            from agentcom.hloop.decisions import calibration
            q = _load_queue()
            spend = SpendLedger(SFILE).totals()
            tiles = tiles_for_status({"programs": []}, hqueue=q,
                                      spend=spend)
            self._json({"tiles": tiles, "counts": agentdeck_state(tiles),
                        "spend": spend,
                        "calibration": calibration(DFILE)})
        elif path == "/api/calibration":
            from agentcom.hloop.decisions import calibration
            self._json(calibration(DFILE))
        elif path == "/api/status":
            from core import module_adapter
            self._json({"status": module_adapter.status("demo"),
                        "provider": {k: (v if k != "model" else v)
                                     for k, v in _provider().items()}})
        elif path == "/api/history":
            self._json(HISTORY[-30:])
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self._gate():
            return
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/chat":
            self._json({"reply": _chat_via_provider(
                str(body.get("message", ""))[:4000])})
        elif path == "/api/answer":
            from agentcom.hloop.decisions import calibration, log_decision
            q = _load_queue()
            t = q.tasks.get(body.get("task_id", ""))
            if not t:
                self._json({"ok": False, "error": "unknown task"}, 404)
                return
            try:
                if t.state == "emitted":
                    t.display()
                if t.state == "displayed":
                    t.acknowledge()
                # Prediction is banked server-side at emit time; the client
                # value is ignored so prediction-before-display always holds.
                value = str(body.get("value", ""))
                t.answer_task(value, t.prediction)
                decision = log_decision(DFILE, t, value)
                _save_queue(q)
                self._json({"ok": True, "state": t.state,
                            "hit": decision["hit"],
                            "action": decision["semantic_action"],
                            "calibration": calibration(DFILE)})
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 400)
        elif path == "/api/vault-store":
            from agentcom.vault.store import Vault
            v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
            value = str(body.get("value", ""))
            if not value:
                self._json({"ok": False, "error": "empty"}, 400)
                return
            out = v.store(str(body.get("name", "LLM_KEY")), value,
                          ["dashboard-chat", "pi-redteam"],
                          ["chat-session", "lane-1"],
                          scope=str(body.get("scope", "")),
                          ttl_s=int(body.get("ttl_s", 86400)),
                          max_uses=int(body.get("max_uses", 0)))
            self._json({"ok": True, **out})
        elif path == "/api/provider":
            os.makedirs(RUNS, exist_ok=True)
            json.dump({"base_url": str(body.get("base_url", ""))[:200],
                       "model": str(body.get("model", ""))[:200]},
                      open(PFILE, "w"))
            self._json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8791"))
    print(f"dashboard token: {TOKEN}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
