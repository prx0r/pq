"""Dashboard — talk to Muse, dispatch sub-agents, see results.

Simple. You chat, the LLM decides what to do, sub-agents run in
background, everything logs to runs/. No rigid workflows.
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
PFILE = os.path.join(RUNS, "provider.json")
SYSFILE = os.path.join(RUNS, "system_prompt.txt")
HISTORY: list[dict] = []

DEFAULT_SYSTEM = """You are an autonomous agent with access to on-chain tools.

TOOLS (call with TOOL: <name> <args>):
- whale_feed [min_usd] — large BTC/ETH transactions, find funded wallets
- eth_check <address> — ETH + ERC-20 balance check
- sol_check <address> — SOL + SPL balance check
- wallet_investigate <address> — full OSINT: ENS, Farcaster, Lens, FOMO, GitHub
- wallet_github address <addr> — search GitHub for wallet address in code
- wallet_github keys <type> — search GitHub for leaked keys
- fomo_leaderboard leaderboard — top traders from fomo.family
- fomo_leaderboard lookup <handle> — resolve trader to wallet
- clone_scan <repo_url> — clone repo + scan for secrets
- classify <secret> — detect key type (eth_key, solana_key, mnemonic, etc)
- drain_classify <secret> — drain authority + actions

You can dispatch sub-agents to run investigations in background.
Be concise. One tool call per message. When you find something interesting, tell me."""


def _load_sys():
    if os.path.exists(SYSFILE):
        try:
            return open(SYSFILE).read().strip()
        except Exception:
            pass
    return DEFAULT_SYSTEM

def _save_sys(text):
    os.makedirs(os.path.dirname(SYSFILE) or ".", exist_ok=True)
    with open(SYSFILE, "w") as f:
        f.write(text)

def _provider():
    if os.path.exists(PFILE):
        return json.load(open(PFILE))
    return {"base_url": cfg.llm_base_url(), "model": cfg.llm_model()}

def _resp_text(resp):
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    return "".join(parts) if parts else resp.get("output_text", "")


def _chat(message: str) -> str:
    """Send message to LLM, return response. Handles tool dispatch."""
    from agentcom.vault.store import Vault
    prov = _provider()
    if not prov.get("model"):
        return "No model configured. Set it in the config panel."
    v = Vault(cfg.vault_path())
    usable = v.find(kind="llm-inference", tier="paid")
    if not usable:
        return "No API key. Paste one in the config panel."
    key = key_name = None
    for c in usable:
        try:
            key = v.resolve(c["name"], "dashboard-chat", "chat-session", c["capability"])
            key_name = c["name"]; break
        except ValueError:
            continue
    if not key:
        return "All keys spent. Deposit a fresh one."

    model = prov["model"]
    base = prov["base_url"].rstrip("/")
    sys_prompt = _load_sys()

    if model.startswith("muse-spark"):
        body = json.dumps({"model": model,
            "input": [{"role": "system", "content": sys_prompt},
                      *HISTORY[-20:],
                      {"role": "user", "content": message}],
            "stream": False, "max_output_tokens": 1024}).encode()
        url = base + "/responses"
    else:
        body = json.dumps({"model": model,
            "messages": [{"role": "system", "content": sys_prompt},
                         *HISTORY[-20:],
                         {"role": "user", "content": message}]}).encode()
        url = base + "/chat/completions"

    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
        text = _resp_text(resp) if model.startswith("muse-spark") else resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"

    HISTORY.append({"role": "user", "content": message})
    HISTORY.append({"role": "assistant", "content": text})

    # If LLM called a tool, dispatch it as a background mission
    _dispatch_tools(text)
    return text


def _dispatch_tools(text: str):
    """Parse TOOL: calls from LLM output, run them in background."""
    import re
    from agentcom.missions import MissionControl
    from agentcom.worker import run_worker

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
                r = run_worker(objective, tools=[tn], max_turns=5, force=True)
                if r.get("ok"):
                    mc.complete(mid, r, findings=r.get("findings", []),
                                tokens_in=r.get("tokens_in",0), tokens_out=r.get("tokens_out",0))
                else:
                    mc.fail(mid, r.get("error","unknown"))
            except Exception as e:
                mc.fail(mid, str(e))

        threading.Thread(target=_run, daemon=True).start()


class H(BaseHTTPRequestHandler):
    server_version = "pq/0.3"

    def _gate(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] != TOKEN:
            self.send_response(401); self.end_headers()
            self.wfile.write(b"bad token"); return False
        return True

    def _json(self, obj, code=200):
        d = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.end_headers(); self.wfile.write(d)

    def _body(self):
        try: n = int(self.headers.get("Content-Length", 0))
        except: n = 0
        if not n: return {}
        try: return json.loads(self.rfile.read(n))
        except: return {}

    def do_GET(self):
        if not self._gate(): return
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            data = open(os.path.join(ROOT, "dashboard", "static", "index.html"), "rb").read()
            self.send_response(200); self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data)
        elif p == "/api/system-prompt": self._json({"prompt": _load_sys()})
        elif p == "/api/missions":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            self._json({"missions": mc.list_missions(), "summary": mc.summary()})
        elif p == "/api/prizes":
            from agentcom.prizes import PrizeStore
            ps = PrizeStore()
            self._json({"prizes": ps.list_prizes(), "summary": ps.summary()})
        elif p == "/api/seen":
            from agentcom.seen import SeenTracker
            st = SeenTracker()
            self._json({"stats": st.stats()})
        elif p == "/api/rsi":
            from agentcom.rsi import analyze, format_insights
            i = analyze()
            self._json({"text": format_insights(i)})
        elif p == "/api/history": self._json(HISTORY[-30:])
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        if not self._gate(): return
        p = urlparse(self.path).path; b = self._body()
        if p == "/api/chat":
            self._json({"reply": _chat(str(b.get("message",""))[:4000])})
        elif p == "/api/system-prompt":
            _save_sys(str(b.get("prompt",""))[:10000])
            self._json({"ok": True})
        elif p == "/api/provider":
            os.makedirs(RUNS, exist_ok=True)
            json.dump({"base_url": str(b.get("base_url",""))[:200],
                       "model": str(b.get("model",""))[:200]}, open(PFILE, "w"))
            self._json({"ok": True})
        elif p == "/api/vault-store":
            from agentcom.vault.store import Vault
            v = Vault(cfg.vault_path())
            val = str(b.get("value",""))
            if not val: self._json({"ok": False, "error": "empty"}, 400); return
            out = v.store(str(b.get("name","LLM_KEY")), val,
                          ["dashboard-chat"], ["chat-session"],
                          ttl_s=86400)
            self._json({"ok": True, **out})
        elif p == "/api/missions/dispatch":
            from agentcom.missions import MissionControl
            from agentcom.worker import run_worker
            mc = MissionControl()
            obj = str(b.get("objective",""))[:2000]
            if not obj: self._json({"ok": False, "error": "no objective"}, 400); return
            m = mc.dispatch(obj, tools=b.get("tools",[]))
            def _run():
                mc.start(m.id)
                try:
                    r = run_worker(obj, tools=b.get("tools",[]),
                                   max_turns=int(b.get("max_turns",8)),
                                   force=b.get("force",False),
                                   wallet_address=str(b.get("wallet_address","")))
                    if r.get("ok"): mc.complete(m.id, r, findings=r.get("findings",[]))
                    else: mc.fail(m.id, r.get("error","unknown"))
                except Exception as e: mc.fail(m.id, str(e))
            threading.Thread(target=_run, daemon=True).start()
            self._json({"ok": True, "mission_id": m.id})
        else: self.send_response(404); self.end_headers()

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8791"))
    print(f"token: {TOKEN}"); print(f"http://localhost:{port}/?token={TOKEN}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
