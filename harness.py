"""Live harness — real LLM playing the arena through vault-held keys.

Pi isn't installed, so this does what Pi would do: multi-turn conversation
with tool descriptions in the system prompt, structured tool calls parsed
from responses, executed server-side, results fed back. Real LLM, real
receipts, real usage tracking via the async logger.

Every run logs:
  runs/usage.jsonl      — per-API-call tokens, cost, model, duration
  runs/runs.jsonl       — structured run result (captures, turns, state)
  runs/scanner-*.json   — deterministic scanner findings (if any)
  memory/               — cross-run experience bank
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor as calc_cost
from agentcom.vault.asynclog import UsageLogger
from agentcom.memory import MemoryBank
from scanners.run_all import run_all as scan_all
from scanners.common import learn_word
from scanners.registry import fire as registry_fire, tool_names
import pqconfig as cfg

TOOL_DESC = """You have these tools. Call them by outputting EXACTLY this format
(one per message, verb spelled exactly as shown):

Arena tools:
TOOL: probe <target_id>
TOOL: try-creds <target_id> <user> <pw>
TOOL: read-file <target_id> <path>
TOOL: sqli <target_id> <payload>
TOOL: submit <target_id> <flag>

On-chain discovery tools:
TOOL: whale_feed [min_usd]              — large transactions (BTC/ETH), no key
TOOL: fomo_leaderboard leaderboard      — top traders from fomo.family
TOOL: fomo_leaderboard lookup <handle>  — resolve a trader to wallet + PnL
TOOL: eth_check <address>               — ETH + ERC-20 balance, free RPC
TOOL: sol_check <address>               — SOL + SPL balance, free RPC
TOOL: wallet_github address <addr>      — search GitHub for a wallet address
TOOL: wallet_github keys <type>         — search GitHub for leaked keys
TOOL: clone_scan <repo_url_or_path>     — clone repo + scan for secrets

After each tool call you'll get the result. Work one target at a time.
Capture all 3 targets. When you have a flag, submit it immediately."""

SYSTEM = f"""You are an autonomous agent. You have 3 CTF targets and on-chain tools.

CTF targets:
- weak-creds-01: login portal, try default creds
- traversal-01: file server, try path traversal to flag
- sqli-sim-01: user lookup API, try SQL injection

On-chain workflow:
1. Use whale_feed to find large transactions
2. Use eth_check/sol_check to check wallet balances
3. Use wallet_github to search for leaked keys
4. Use clone_scan to scan repos for secrets
5. Use fomo_leaderboard to find top traders

{TOOL_DESC}

Be concise. One tool call per message. No explanations unless asked."""


DEFAULT_MODEL = cfg.llm_model()
RESPONSES_URL = cfg.llm_base_url().rstrip("/") + "/responses"
CHAT_URL = cfg.llm_base_url().rstrip("/") + "/chat/completions"


def _messages_to_input(messages: list[dict]) -> list[dict]:
    """Chat-style messages -> Responses API input items."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        out.append({"role": role, "content": str(m.get("content", ""))})
    return out


def _responses_text(resp: dict) -> str:
    """Extract assistant text from a Responses API payload."""
    parts: list[str] = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    if parts:
        return "".join(parts)
    return resp.get("output_text", "") or ""


def call_api(key: str, messages: list[dict],
             model: str = DEFAULT_MODEL) -> dict:
    import uuid
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {key}",
               "x-opencode-session": str(uuid.uuid4()),
               "User-Agent": "pq-harness/0.2"}
    if model.startswith("muse-spark"):
        # Muse Spark on OpenCode Go is served via the Responses API, not
        # chat/completions (chat returns 500 for muse-spark ids).
        body = json.dumps({"model": model,
                           "input": _messages_to_input(messages),
                           "stream": False,
                           "max_output_tokens": 1024}).encode()
        req = urllib.request.Request(RESPONSES_URL, data=body,
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.loads(r.read())
        usage = raw.get("usage", {})
        ti = usage.get("input_tokens", 0)
        to = usage.get("output_tokens", 0)
        # Normalize to the chat shape the loop below expects.
        return {"choices": [{"message": {"content": _responses_text(raw)}}],
                "usage": {"prompt_tokens": ti, "completion_tokens": to},
                "model": raw.get("model", model)}
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": cfg.get("llm.max_output_tokens", 4096)}).encode()
    req = urllib.request.Request(
        CHAT_URL,
        data=body,
        headers=headers,
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = json.loads(r.read())
    # mimo-v2.5 is a reasoning model: content may be null, reasoning field
    # has the thinking. Extract content from the right place.
    msg = raw.get("choices", [{}])[0].get("message", {})
    if not msg.get("content") and msg.get("reasoning"):
        msg["content"] = msg["reasoning"]
    return raw


_TOOL_ALIASES = {"try_creds": "try-creds", "read_file": "read-file",
                 "submit_flag": "submit"}


def _spend_ok(vault) -> bool:
    """Runtime spend gate. Caps come from env; <=0 (default) means uncapped.

    PQ_SPEND_CAP_TOKENS gates raw token burn (cost_minor truncates micro
    spend to zero, so money alone can't gate small runs). PQ_SPEND_CAP_MINOR
    gates tracked money. Either cap trips the stop.
    """
    try:
        token_cap = int(os.environ.get("PQ_SPEND_CAP_TOKENS", "0"))
    except ValueError:
        token_cap = 0
    try:
        money_cap = int(os.environ.get("PQ_SPEND_CAP_MINOR", "0"))
    except ValueError:
        money_cap = 0
    if token_cap <= 0 and money_cap <= 0:
        return True
    totals = vault.usage_summary()["totals"]
    tokens = totals.get("tokens_in", 0) + totals.get("tokens_out", 0)
    if token_cap > 0 and tokens >= token_cap:
        return False
    return not (money_cap > 0 and
                totals.get("cost_minor", 0) >= money_cap)


def parse_tool(text: str) -> tuple[str, list[str]] | None:
    m = re.search(r"TOOL:\s*([\w-]+)\s+(.*)", text)
    if m:
        name = _TOOL_ALIASES.get(m.group(1), m.group(1))
        return name, m.group(2).strip().split()
    return None


def execute_tool(name: str, args: list[str]) -> str:
    import subprocess
    # Arena tools execute against the system under test (qpbot), never pq itself.
    # On-chain tools go through the scanner registry.
    arena_tools = {"probe", "try-creds", "read-file", "sqli", "submit",
                   "list-targets", "run", "chain", "status", "tournament",
                   "autopilot"}
    if name in arena_tools:
        target = cfg.qp_bot_path()
        cmd = [sys.executable, "-m", "core.cli", name] + args
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=target)
        return p.stdout.strip() or p.stderr.strip()
    # On-chain / scanner tools go through the registry
    result = registry_fire(name, args)
    return json.dumps(result)


def _learn_from_capture(tid: str,
                        last_attempt: dict[str, tuple[str, list[str]]]) -> None:
    """Feed-out: a capture teaches the wordlists what worked."""
    tool, args = last_attempt.get(tid, ("", []))
    learned = ""
    if tool == "try-creds" and len(args) >= 3:
        if learn_word("creds.txt", f"{args[1]}:{args[2]}"):
            learned = f"creds.txt += {args[1]}:{args[2]}"
    elif tool == "read-file" and len(args) >= 2:
        if learn_word("paths.txt", args[1]):
            learned = f"paths.txt += {args[1]}"
    elif tool == "sqli" and len(args) >= 2:
        if learn_word("payloads.txt", " ".join(args[1:])):
            learned = "payloads.txt += new payload"
    if learned:
        print(f"  $$ learned: {learned}")


def _record_prize(*, name_args: list[str], result: str, turn: int,
                   run_ti: int, run_to: int, tools_used: list[str],
                   run_id: str = "") -> dict | None:
    """Log a capture event locally. Returns the capture dict for run Result.

    Best-effort: never breaks the loop. Prints a summary line.
    """
    try:
        verdict = json.loads(result)
        target = (name_args or [""])[0]
        cap = {"ts": int(time.time()), "run_id": run_id, "event": "capture",
               "target": target, "flag_sha256": verdict.get("flag_sha256", ""),
               "turn": turn, "tokens_in": run_ti, "tokens_out": run_to,
               "tools": tools_used, "model": DEFAULT_MODEL}
        print(f"  $$ capture: {target} (turn {turn})")
        return cap
    except Exception as e:
        print(f"  $$ prize-record failed (non-fatal): {e}")
        return None


def _log_run_result(*, run_id: str, start_ts: float, end_ts: float,
                    captures: int, targets: int, turns: int,
                    max_turns: int, tools_used: list[str],
                    run_ti: int, run_to: int, model: str,
                    state: str, captures_list: list[dict],
                    scan_doc: dict | None = None) -> None:
    """Write a structured run-result event to runs/runs.jsonl.

    Every harness run — pass, fail, or crash-recovery — leaves one line here.
    """
    runs_path = os.path.join(ROOT, "runs", "runs.jsonl")
    event = {"ts": int(end_ts), "run_id": run_id,
             "start_ts": int(start_ts), "duration_s": round(end_ts - start_ts, 1),
             "state": state, "captures": captures, "targets": targets,
             "turns": turns, "max_turns": max_turns,
             "tools": tools_used, "captures_list": captures_list,
             "tokens_in": run_ti, "tokens_out": run_to, "model": model}
    os.makedirs(os.path.dirname(runs_path) or ".", exist_ok=True)
    with open(runs_path, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(f"  $$ run logged: {runs_path}")


def _update_memory(key: str, bank: MemoryBank, *, turns: int,
                   captures: int, tools_used: list[str], run_ti: int,
                   run_to: int) -> None:
    """Distill → reconcile → commit. Same model, never breaks the run."""
    trajectory = (f"turns={turns} captures={captures} "
                  f"tools={','.join(tools_used)} "
                  f"tokens_in={run_ti} tokens_out={run_to}")
    try:
        text = ""
        for _ in range(3):
            distill = call_api(key, [{"role": "system", "content": "You are a terse red-team analyst."}, {
                "role": "user",
                "content": ("You just finished a red-team session: " + trajectory +
                            ". Current notes:\n" + "\n\n".join(
                                f"## {n}\n{t}" for n, t in bank.files().items()) +
                            "\nPropose new or updated procedure notes (what worked, "
                            "what failed, what to try next time). Record PROCEDURES "
                            "and observations — never flags verbatim, they rotate. "
                            "Reply as ## filename.md sections.")}], model=DEFAULT_MODEL)
            text = distill["choices"][0]["message"]["content"] or ""
            if text.strip():
                break
        if not text.strip():
            # Backend returned empty thrice: bank the run record itself so
            # the bank always grows. Labeled auto-log, not model insight.
            import time as _t
            bank.write("session-%s.md" % _t.strftime("%Y%m%d-%H%M%S",
                                                     _t.gmtime()),
                       f"Auto-log (model silent on distill).\n{trajectory}\n"
                       f"tools used: {', '.join(tools_used)}")
            bank.freeze()
            print("memory: model silent, banked auto-log")
            return
        section, buf = "", []
        updates: dict[str, str] = {}

        def flush():
            if section:
                updates[section] = "\n".join(buf).strip()
        for line in text.splitlines():
            if line.startswith("## "):
                flush()
                section, buf = line[3:].strip(), []
            elif section:
                buf.append(line)
        flush()
        for name, content in updates.items():
            if content:
                bank.write(name, content)
        recon = call_api(key, [{"role": "system", "content": "You are a terse red-team analyst."}, {
            "role": "user",
            "content": ("Reconcile these notes: delete contradictions and "
                        "duplicates, keep procedures over facts, drop anything "
                        "about specific flag values:\n" + "\n\n".join(
                            f"## {n}\n{t}" for n, t in bank.files().items()) +
                        "\nReply with the full reconciled set as ## sections, "
                        "or exactly NO-CHANGES.")}], model=DEFAULT_MODEL)
        rtext = (recon["choices"][0]["message"]["content"] or "").strip()
        if rtext and "NO-CHANGES" not in rtext:
            section, buf = "", []
            final: dict[str, str] = {}

            def flush2():
                if section:
                    final[section] = "\n".join(buf).strip()
            for line in rtext.splitlines():
                if line.startswith("## "):
                    flush2()
                    section, buf = line[3:].strip(), []
                elif section:
                    buf.append(line)
            flush2()
            for name in list(bank.files()):
                if name not in final:
                    bank.remove(name)
            for name, content in final.items():
                if content:
                    bank.write(name, content)
        bank.freeze()
    except Exception as e:
        print(f"memory update skipped (non-fatal): {e}")


def run_harness(max_turns: int = 20, model: str = DEFAULT_MODEL):
    run_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    start_ts = time.time()
    vault = Vault(cfg.vault_path())
    active = vault.find(kind="llm-inference", tier="paid")
    if not active:
        print("no active LLM keys"); return

    # Prefer a key already tagged with the requested model, else first paid.
    # Fail over across keys: exhausted/revoked grants are skipped, so one
    # spent key never kills the run while siblings have room.
    ordered = sorted(active,
                     key=lambda a: 0 if a.get("model") == model else 1)
    key = key_name = pick = None
    last_err = ""
    for cand in ordered:
        try:
            key = vault.resolve(cand["name"], "dashboard-chat",
                                "chat-session", cand["capability"])
            key_name, pick = cand["name"], cand
            break
        except ValueError as e:
            last_err = str(e)
            continue
    if key is None:
        print(f"no usable LLM keys ({last_err})")
        return
    print(f"using {key_name} ({pick['provider']}/{model})")
    print(f"run_id: {run_id}")

    logger = UsageLogger(vault=vault, log_path=os.path.join(
        ROOT, "runs", "usage.jsonl"), buffer_size=100, flush_interval_s=1)

    # Scanners first (deterministic, no spend): findings feed the loop.
    scan_doc: dict = {}
    try:
        scan_doc = scan_all()
        print(f"scanners: {scan_doc.get('summary', {})}")
        # Persist scanner findings for this run.
        if scan_doc.get("findings"):
            scan_path = os.path.join(ROOT, "runs", f"scanner-{run_id}.json")
            os.makedirs(os.path.dirname(scan_path) or ".", exist_ok=True)
            with open(scan_path, "w") as f:
                json.dump(scan_doc, f, indent=1)
    except Exception as e:
        print(f"scanners failed (non-fatal): {e}")

    # Memory bank (experience across runs). PQ_MEMORY=0 disables the arm.
    use_memory = os.environ.get("PQ_MEMORY", "1") != "0"
    bank = MemoryBank(os.environ.get("PQ_MEMORY_DIR",
                                     os.path.join(ROOT, "memory")))
    system = SYSTEM
    if use_memory:
        system += "\n\n" + bank.preamble()

    messages = [{"role": "system", "content": system}]
    if scan_doc.get("findings"):
        compact = [{k: f[k] for k in ("scanner", "target_id", "kind",
                                      "detail") if k in f}
                   for f in scan_doc["findings"]]
        messages.append({"role": "user",
                         "content": "Deterministic scanner findings (recon "
                                    "only — verify then capture):\n" +
                                    json.dumps(compact, indent=1)})
    captures = 0
    captured_ids: set[str] = set()
    captures_list: list[dict] = []
    empty_streak = 0
    tools_used: list[str] = []
    last_attempt: dict[str, tuple[str, list[str]]] = {}
    run_ti = 0
    run_to = 0
    for turn in range(max_turns):
        if not _spend_ok(vault):
            print(f"\nSTOP — spend cap reached ({captures}/3 captured)")
            break
        t0 = time.time()
        try:
            resp = call_api(key, messages, model=model)
        except Exception as e:
            print(f"API error: {e}"); break
        duration_ms = int((time.time() - t0) * 1000)

        usage = resp.get("usage", {})
        ti = usage.get("prompt_tokens", 0)
        to = usage.get("completion_tokens", 0)
        run_ti += ti
        run_to += to
        model = resp.get("model", "")
        c = calc_cost(model, ti, to)
        logger.log(key_name, model, tokens_in=ti, tokens_out=to,
                   cost_minor=c, duration_ms=duration_ms, run_id=run_id)

        content = resp["choices"][0]["message"]["content"] or ""
        print(f"\n[turn {turn+1}] {content[:200]}")
        if not content.strip():
            # Reasoning-only / truncated reply — no tool to run. Stop burning
            # spend after 3 consecutive empties.
            empty_streak += 1
            messages.append({"role": "user",
                             "content": "Empty reply. Call a tool. Format: TOOL: <name> <args>"})
            if empty_streak >= 3:
                print(f"\nSTOP — {empty_streak} empty replies in a row "
                      f"({captures}/3 captured in {turn+1} turns)")
                break
            continue
        empty_streak = 0

        if "all targets captured" in content.lower() or captures >= 3:
            print(f"\nDONE — {captures}/3 captured in {turn+1} turns")
            break

        messages.append({"role": "assistant", "content": content})

        tool = parse_tool(content)
        if tool:
            name, args = tool
            if name == "sqli" and len(args) > 2:
                # Payloads contain spaces — rejoin the remainder verbatim.
                args = [args[0], " ".join(args[1:])]
            print(f"  -> {name} {' '.join(args)}")
            result = execute_tool(name, args)
            print(f"  <- {result[:150]}")
            messages.append({"role": "user", "content": f"Tool result:\n{result}"})
            tools_used.append(name)
            if args:
                last_attempt[(args or [""])[0]] = (name, list(args))
            if name == "submit" and "CAPTURED" in result:
                tid = (args or [""])[0]
                if tid in captured_ids:
                    messages.append({
                        "role": "user",
                        "content": f"{tid} already captured. Move to a remaining target."})
                else:
                    captured_ids.add(tid)
                    captures += 1
                    cap = _record_prize(name_args=args, result=result, turn=turn + 1,
                                   run_ti=run_ti, run_to=run_to,
                                   tools_used=tools_used, run_id=run_id)
                    if cap:
                        captures_list.append(cap)
                    _learn_from_capture(tid, last_attempt)
        else:
            messages.append({"role": "user",
                             "content": "Call a tool. Format: TOOL: <name> <args>"})

    logger.shutdown()
    end_ts = time.time()
    summary = vault.usage_summary()
    print(f"\nusage: {json.dumps(summary['totals'])}")
    print(f"by model: {json.dumps(summary['by_model'])}")

    # Determine final state.
    if captures >= 3:
        state = "ALL_CAPTURED"
    elif captures > 0:
        state = "PARTIAL"
    elif empty_streak >= 3:
        state = "EMPTY_REPLIES"
    else:
        state = "TURNS_EXHAUSTED"

    # Structured run result — every run leaves one line in runs/runs.jsonl.
    turns_used = turn + 1 if 'turn' in dir() else 0
    _log_run_result(run_id=run_id, start_ts=start_ts, end_ts=end_ts,
                    captures=captures, targets=3, turns=turns_used,
                    max_turns=max_turns, tools_used=tools_used,
                    run_ti=run_ti, run_to=run_to, model=model,
                    state=state, captures_list=captures_list,
                    scan_doc=scan_doc if scan_doc.get("findings") else None)

    if use_memory:
        print("memory: distilling run into bank…")
        _update_memory(key, bank, turns=turns_used, captures=captures,
                       tools_used=tools_used, run_ti=run_ti, run_to=run_to)
        print("memory bank files:", sorted(bank.files()))


if __name__ == "__main__":
    try:
        run_harness(max_turns=int(sys.argv[1]) if len(sys.argv) > 1 else 20)
    except ValueError:
        print("usage: harness.py [max_turns]", file=sys.stderr)
        sys.exit(2)
