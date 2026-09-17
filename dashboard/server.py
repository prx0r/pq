"""Dashboard — chat left, H-task rail right. Muse-native. Stdlib only.

Token gate: every request needs ?token=<DASH_TOKEN> (env or generated at
boot, printed once to stdout). Binds loopback; the outside world arrives
only through the Cloudflare tunnel.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TOKEN = os.environ.get("DASH_TOKEN", secrets.token_urlsafe(24))
RUNS = os.path.join(ROOT, "runs")
HFILE = os.path.join(RUNS, "htasks.json")
PFILE = os.path.join(RUNS, "provider.json")
SYSFILE = os.path.join(RUNS, "system_prompt.txt")
HISTORY: list[dict] = []

DEFAULT_SYSTEM = """You are the qpbot conversational assistant. Autonomous red-team
work runs beside this chat. You have access to on-chain tools via the
mission dispatch system. Answer directly and briefly. When you find
something interesting, tell me."""


def _load_sys() -> str:
    if os.path.exists(SYSFILE):
        try:
            return open(SYSFILE).read().strip()
        except Exception:
            pass
    return DEFAULT_SYSTEM


def _save_sys(text: str):
    os.makedirs(os.path.dirname(SYSFILE) or ".", exist_ok=True)
    with open(SYSFILE, "w") as f:
        f.write(text)


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
    return {"base_url": "https://opencode.ai/zen/go/v1", "model": "mimo-v2.5"}


def _resp_text(resp: dict) -> str:
    """Extract text from Muse responses API or OpenAI chat completions."""
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    if parts:
        return "".join(parts)
    return resp.get("output_text", "")


def _chat_via_provider(message: str) -> str:
    from agentcom.vault.store import Vault
    prov = _provider()
    if not prov.get("model"):
        return ("No model configured. Set provider + model below, then "
                "deposit your key in the rail — chat goes live after that.")
    v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    usable = v.find(kind="llm-inference", tier="paid")
    if not usable:
        return ("No key in the vault yet. Paste it into the rail's secret "
                "box (it never touches chat) and try again.")
    key = key_name = None
    for c in usable:
        try:
            key = v.resolve(c["name"], "dashboard-chat", "chat-session",
                            c["capability"])
            key_name = c["name"]
            break
        except ValueError:
            continue
    if not key:
        return "All keys exhausted. Deposit a fresh one."

    model = prov["model"]
    base = prov["base_url"].rstrip("/")
    sys_prompt = _load_sys()

    if model.startswith("muse-spark"):
        body = json.dumps({
            "model": model,
            "input": [{"role": "system", "content": sys_prompt},
                      *HISTORY[-20:],
                      {"role": "user", "content": message}],
            "stream": False,
            "max_output_tokens": 1024,
        }).encode()
        url = base + "/responses"
    else:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "system", "content": sys_prompt},
                         *HISTORY[-20:],
                         {"role": "user", "content": message}],
        }).encode()
        url = base + "/chat/completions"

    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        if model.startswith("muse-spark"):
            text = _resp_text(resp)
        else:
            text = resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Provider call failed: {type(e).__name__}: {e}"

    HISTORY.append({"role": "user", "content": message})
    HISTORY.append({"role": "assistant", "content": text})

    _dispatch_tools(text)
    return text


def _dispatch_tools(text: str):
    """Parse TOOL: calls from LLM output, run them in background."""
    from agentcom.missions import MissionControl
    matches = re.findall(r"TOOL:\s*([\w-]+)\s+(.*)", text)
    if not matches:
        return
    mc = MissionControl()
    for tool, args in matches[:3]:
        objective = f"{tool} {args}"
        m = mc.dispatch(objective, tools=[tool])

        def _run(mid=m.id, tn=tool, ta=args):
            mc.start(mid)
            try:
                import subprocess
                cmd = [sys.executable, "-m", "core.cli", tn] + ta.split()
                p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                result = {"ok": p.returncode == 0,
                          "stdout": p.stdout.strip()[:2000],
                          "stderr": p.stderr.strip()[:500]}
                mc.complete(mid, result, findings=[{"tool": tn, "args": ta, "data": result}])
            except Exception as e:
                mc.fail(mid, str(e))

        threading.Thread(target=_run, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "qpbot-dash/0.2"

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
                        "provider": _provider()})
        elif path == "/api/system-prompt":
            self._json({"prompt": _load_sys()})
        elif path == "/api/missions":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            self._json({"missions": mc.list_missions(), "summary": mc.summary()})
        elif path == "/api/prizes":
            from agentcom.prizes import PrizeStore
            ps = PrizeStore()
            self._json({"prizes": ps.list_prizes(), "summary": ps.summary()})
        elif path == "/api/seen":
            from agentcom.seen import SeenTracker
            st = SeenTracker()
            self._json({"stats": st.stats()})
        elif path == "/api/rsi":
            from agentcom.rsi import analyze, format_insights
            i = analyze()
            self._json({"text": format_insights(i)})
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
        elif path == "/api/system-prompt":
            _save_sys(str(body.get("prompt", ""))[:10000])
            self._json({"ok": True})
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
        elif path == "/api/missions/dispatch":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            obj = str(body.get("objective", ""))[:2000]
            if not obj:
                self._json({"ok": False, "error": "no objective"}, 400)
                return
            m = mc.dispatch(obj, tools=body.get("tools", []))

            def _run():
                mc.start(m.id)
                try:
                    import subprocess
                    tool_args = obj.split()
                    cmd = [sys.executable, "-m", "core.cli"] + tool_args
                    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                    result = {"ok": p.returncode == 0,
                              "stdout": p.stdout.strip()[:2000],
                              "stderr": p.stderr.strip()[:500]}
                    mc.complete(m.id, result, findings=[{"data": result}])
                except Exception as e:
                    mc.fail(m.id, str(e))

            threading.Thread(target=_run, daemon=True).start()
            self._json({"ok": True, "mission_id": m.id})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8791"))
    print(f"dashboard token: {TOKEN}", flush=True)
    print(f"http://localhost:{port}/?token={TOKEN}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
