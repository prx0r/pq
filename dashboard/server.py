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
HISTORY: list[dict] = []


def _load_tasks() -> list[dict]:
    if os.path.exists(HFILE):
        return json.load(open(HFILE))
    seed = [
        {"task_id": "demo-digit-1", "kind": "digit",
         "question": "Demo pack finished 3/3. Which lane should lead next?",
         "prediction": "7", "confidence": 0.72, "state": "displayed",
         "context_hash": "seed", "campaign": "demo", "lane": "creds-first",
         "deadline": 4102444800, "answer": None},
        {"task_id": "demo-approval-1", "kind": "confirm",
         "question": "Approve running the live Pi red-team lane? (no spend yet)",
         "prediction": "", "confidence": 0.0, "state": "emitted",
         "context_hash": "seed", "campaign": "demo", "lane": "pi",
         "deadline": 4102444800, "answer": None},
    ]
    os.makedirs(RUNS, exist_ok=True)
    json.dump(seed, open(HFILE, "w"), indent=1)
    return seed


def _save_tasks(tasks: list[dict]):
    os.makedirs(RUNS, exist_ok=True)
    json.dump(tasks, open(HFILE, "w"), indent=1)


def _provider() -> dict:
    if os.path.exists(PFILE):
        return json.load(open(PFILE))
    return {"base_url": "https://api.openai.com/v1", "model": ""}


def _chat_via_provider(message: str) -> str:
    from agentcom.vault.store import Vault
    prov = _provider()
    if not prov.get("model"):
        return ("No model configured. Set provider + model below, then "
                "deposit your key in the rail — chat goes live after that.")
    v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    if not v.credential_available("LLM_KEY"):
        return ("No key in the vault yet. Paste it into the rail's secret "
                "box (it never touches chat) and try again.")
    key = v.resolve("LLM_KEY", "dashboard-chat", "chat-session",
                    v.secrets["LLM_KEY"]["capability"])
    req_body = json.dumps({
        "model": prov["model"],
        "messages": [
            {"role": "system",
             "content": "You are the qpbot conversational assistant. "
                        "Autonomous red-team work runs beside this chat; "
                        "answer directly and briefly."},
            *HISTORY[-10:],
            {"role": "user", "content": message},
        ],
    }).encode()
    req = urllib.request.Request(
        prov["base_url"].rstrip("/") + "/chat/completions", data=req_body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.load(r)
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
            self._json(_load_tasks())
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
            from agentcom.htasks.queue import HQueue, HTask
            q = HQueue()
            for raw in _load_tasks():
                t = HTask(raw["task_id"], raw["kind"], raw["question"],
                          prediction=raw.get("prediction", ""),
                          confidence=raw.get("confidence", 0.0))
                t.state = raw.get("state", "emitted")
                t.context_hash = raw.get("context_hash", "")
                q.emit(t)
            t = q.tasks.get(body.get("task_id", ""))
            if not t:
                self._json({"ok": False, "error": "unknown task"}, 404)
                return
            try:
                if t.state == "emitted":
                    t.display()
                if t.state == "displayed":
                    t.acknowledge()
                t.answer_task(str(body.get("value", "")),
                              str(body.get("prediction", "")))
                _save_tasks([x.view() | {"answer": x.answer}
                             for x in q.tasks.values()])
                self._json({"ok": True, "state": t.state})
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
