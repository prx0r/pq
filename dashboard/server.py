"""Dashboard — chat, missions, system prompt config. Stdlib only.

The main agent interface. You talk to the LLM here, dispatch missions,
see sub-agent results, and configure the system prompt.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pqconfig as cfg

TOKEN = os.environ.get("DASH_TOKEN", secrets.token_urlsafe(24))
RUNS = cfg.runs_dir()
HFILE = os.path.join(RUNS, "htasks.json")
PFILE = os.path.join(RUNS, "provider.json")
DFILE = os.path.join(RUNS, "decisions.jsonl")
SFILE = os.path.join(RUNS, "spend.jsonl")
SYSFILE = os.path.join(RUNS, "system_prompt.txt")
HISTORY: list[dict] = []

DEFAULT_SYSTEM = """You are the pq agent — an autonomous red-team and on-chain intelligence system.

You have access to these tools (call via TOOL: <name> <args>):
- whale_feed [min_usd] — large BTC/ETH transactions
- eth_check <address> — ETH + ERC-20 balance
- sol_check <address> — SOL + SPL balance
- wallet_investigate <address> — full OSINT chain to find identity
- wallet_github address <addr> — search GitHub for wallet address
- wallet_github keys <type> — search for leaked keys
- fomo_leaderboard leaderboard — top traders from fomo.family
- fomo_leaderboard lookup <handle> — resolve trader to wallet
- clone_scan <repo_url> — clone repo + scan for secrets
- classify <secret> — detect key type
- drain_classify <secret> — drain authority + actions

You can also dispatch missions to sub-agents that run autonomously.
Be concise. One tool call per message. Always explain what you found."""


def _load_system_prompt() -> str:
    if os.path.exists(SYSFILE):
        try:
            with open(SYSFILE) as f:
                return f.read().strip()
        except Exception:
            pass
    return DEFAULT_SYSTEM


def _save_system_prompt(text: str):
    os.makedirs(os.path.dirname(SYSFILE) or ".", exist_ok=True)
    with open(SYSFILE, "w") as f:
        f.write(text)


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
    return {"base_url": cfg.llm_base_url(),
            "model": cfg.llm_model()}


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
        return ("No model configured. Set provider + model in the config panel.")
    v = Vault(cfg.vault_path())
    usable = [a for a in v.find(kind="llm-inference", tier="paid")]
    if not usable:
        return ("No key in the vault. Paste your API key in the config panel.")
    key = key_name = None
    for cand in usable:
        try:
            key = v.resolve(cand["name"], "dashboard-chat",
                            "chat-session", cand["capability"])
            key_name = cand["name"]
            break
        except ValueError:
            continue
    if key is None:
        return "Vault keys are all spent or expired. Deposit a fresh key."

    model = prov["model"]
    base = prov["base_url"].rstrip("/")
    system_prompt = _load_system_prompt()

    if model.startswith("muse-spark"):
        req_body = json.dumps({
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                *HISTORY[-20:],
                {"role": "user", "content": message},
            ],
            "stream": False,
            "max_output_tokens": 1024,
        }).encode()
        url = base + "/responses"
    else:
        req_body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *HISTORY[-20:],
                {"role": "user", "content": message},
            ],
            "max_tokens": 512,
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
    except Exception as e:
        return f"Provider call failed: {type(e).__name__}: {e}"

    HISTORY.append({"role": "user", "content": message})
    HISTORY.append({"role": "assistant", "content": text})

    # Auto-dispatch if LLM output contains TOOL: commands
    _maybe_dispatch_from_chat(text)

    return text


def _maybe_dispatch_from_chat(text: str):
    """If the LLM's response contains tool calls, dispatch them as missions."""
    import re
    from agentcom.missions import MissionControl
    from agentcom.worker import run_worker

    tools = re.findall(r"TOOL:\s*([\w-]+)\s+(.*)", text)
    if not tools:
        return

    mc = MissionControl()
    for tool_name, tool_args in tools[:3]:  # max 3 auto-dispatched
        if tool_name in ("whale_feed", "wallet_investigate", "wallet_github",
                         "eth_check", "sol_check", "clone_scan"):
            objective = f"Execute {tool_name} {tool_args}"
            m = mc.dispatch(objective, tools=[tool_name])

            def _run(mid=mid, tn=tool_name, ta=tool_args):
                mc.start(mid)
                try:
                    result = run_worker(objective, tools=[tn], max_turns=3,
                                        force=True)
                    if result.get("ok"):
                        mc.complete(mid, result, findings=result.get("findings", []))
                    else:
                        mc.fail(mid, result.get("error", "unknown"))
                except Exception as e:
                    mc.fail(mid, str(e))

            t = threading.Thread(target=_run, daemon=True)
            t.start()


class Handler(BaseHTTPRequestHandler):
    server_version = "pq-dash/0.3"

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
            q = _load_queue()
            touched = False
            for t in q.tasks.values():
                if t.state == "emitted":
                    t.display()
                    touched = True
            if touched or q.sweep():
                _save_queue(q)
            self._json(_task_list(q))
        elif path == "/api/system-prompt":
            self._json({"prompt": _load_system_prompt()})
        elif path == "/api/missions":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            status = parse_qs(urlparse(self.path).query).get("status", [""])[0]
            self._json({"missions": mc.list_missions(status),
                        "summary": mc.summary()})
        elif path == "/api/prizes":
            from agentcom.prizes import PrizeStore
            ps = PrizeStore()
            self._json({"prizes": ps.list_prizes(), "summary": ps.summary()})
        elif path == "/api/seen":
            from agentcom.seen import SeenTracker
            st = SeenTracker()
            self._json({"seen": st.list_seen(), "stats": st.stats()})
        elif path == "/api/rsi":
            from agentcom.rsi import analyze, format_insights
            insights = analyze()
            self._json({"insights": insights,
                        "text": format_insights(insights)})
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
            prompt = str(body.get("prompt", ""))[:10000]
            _save_system_prompt(prompt)
            self._json({"ok": True, "length": len(prompt)})
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
            v = Vault(cfg.vault_path())
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
            from agentcom.worker import run_worker
            mc = MissionControl()
            objective = str(body.get("objective", ""))[:2000]
            tools = body.get("tools", [])
            max_turns = int(body.get("max_turns", 10))
            force = body.get("force", False)
            wallet_address = str(body.get("wallet_address", ""))[:100]
            if not objective:
                self._json({"ok": False, "error": "no objective"}, 400)
                return
            m = mc.dispatch(objective, tools=tools)
            def _run():
                mc.start(m.id, run_id=f"worker-{m.id}")
                try:
                    result = run_worker(objective, tools=tools,
                                        max_turns=max_turns, force=force,
                                        wallet_address=wallet_address)
                    if result.get("ok"):
                        mc.complete(m.id, result,
                                    findings=result.get("findings", []),
                                    tokens_in=result.get("tokens_in", 0),
                                    tokens_out=result.get("tokens_out", 0))
                    else:
                        mc.fail(m.id, result.get("error", "unknown"))
                except Exception as e:
                    mc.fail(m.id, str(e))
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            self._json({"ok": True, "mission_id": m.id, "status": "queued"})
        elif path == "/api/missions/status":
            mission_id = body.get("mission_id", "")
            from agentcom.missions import MissionControl
            mc = MissionControl()
            m = mc.get(mission_id)
            if not m:
                self._json({"ok": False, "error": "unknown mission"}, 404)
            else:
                self._json({"ok": True, "mission": m.to_dict()})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8791"))
    print(f"dashboard token: {TOKEN}", flush=True)
    print(f"system prompt: {SYSFILE}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
