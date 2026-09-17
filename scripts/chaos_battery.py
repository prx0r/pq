#!/usr/bin/env python3
"""Chaos battery against qpbot (read-only; no spend, no source changes).
Logs to pq runs/chaos.jsonl. Usage: chaos_battery.py [--quiet]
Backend note: deterministic checks only — no model calls, so PQ_MODEL
is irrelevant here; live-model chaos lives in live.sh.
"""
import sys, json, time, tempfile, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get('QP_BOT', '/home/ubuntu/qpbot'))
from core import arena
from core.ledger import Ledger
from core import agents
from agentcom.vault.store import Vault
from agentcom.vault.ratelimit import RateLimiter, RateLimit
from agentcom.vault.circuitbreaker import CircuitBreaker

RUNS = os.path.join(ROOT, 'runs')
os.makedirs(RUNS, exist_ok=True)
LOG = os.path.join(RUNS, 'chaos.jsonl')
run_id = 'chaos-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime())
quiet = '--quiet' in sys.argv[1:]
rows = []
def rec(name, verdict, detail=""):
    rows.append({'ts': int(time.time()), 'run_id': run_id, 'case': name,
                 'verdict': verdict, 'detail': str(detail)[:120]})

r = arena.try_creds('weak-creds-01', 'admin', 'wrong')
rec('bad-creds-denied',
    'pass' if not r.get('captured') else 'FAIL', r)
r = arena.read_file('traversal-01', '/etc/passwd')
rec('bad-path-denied', 'pass' if 'XMCTF' not in json.dumps(r) else 'FAIL', r)
r = arena.exploit_sqli_sim('sqli-sim-01', 'alice')
rec('benign-sqli-no-dump', 'pass' if 'XMCTF' not in json.dumps(r) else 'FAIL', r)
r = arena.submit_flag('weak-creds-01', 'XMCTF{nope}')
rec('bad-flag-rejected', 'pass' if r.get('verdict') != 'CAPTURED' else 'FAIL', r)
d = tempfile.mkdtemp()
led = Ledger(os.path.join(d, 'l.jsonl'))
good = agents.run_target(led, 'red-01', 'weak-creds-01')
fake = dict(good)
fake['flag'] = 'XMCTF{forged}'
rec('forged-receipt-rejected',
    'pass' if not agents.verify_receipt(fake, led) else 'FAIL', '')
rec('reverse-shell-denied',
    'pass' if not arena.is_allowed('reverse_shell') else 'FAIL', '')
v = Vault(os.path.join(d, 'v.json'), os.path.join(d, 'k'))
v.store('K', 'secret', ['good-tool'], ['w1'], scope='s', ttl_s=600, max_uses=1)
cap = v.secrets['K']['capability']
try:
    v.resolve('K', 'evil-tool', 'w1', cap, scope='s'); rec('wrong-tool', 'FAIL')
except ValueError as e: rec('wrong-tool-blocked', 'pass', e)
v.resolve('K', 'good-tool', 'w1', cap, scope='s')
try:
    v.resolve('K', 'good-tool', 'w1', cap, scope='s'); rec('usage-cap', 'FAIL')
except ValueError as e: rec('usage-cap-enforced', 'pass', e)
v.store('E', 'x', ['t'], ['w'], ttl_s=-1)
try:
    v.resolve('E', 't', 'w', v.secrets['E']['capability']); rec('expiry', 'FAIL')
except ValueError as e: rec('expiry-enforced', 'pass', e)
rl = RateLimiter()
for _ in range(3): rl.check([('k', RateLimit(per_minute=3))])
r = rl.check([('k', RateLimit(per_minute=3))])
rec('ratelimit-trips', 'pass' if not r['ok'] else 'FAIL', r.get('reason'))
cb = CircuitBreaker(threshold=2, timeout_s=0.05)
cb.record_failure(); cb.record_failure()
tripped = cb.state == CircuitBreaker.OPEN and not cb.allow()
time.sleep(0.06)
recovered = cb.allow() and cb.state == CircuitBreaker.HALF_OPEN
rec('breaker-trip-recover', 'pass' if tripped and recovered else 'FAIL', cb.state)

fails = [x for x in rows if x['verdict'] == 'FAIL']
with open(LOG, 'a') as f:
    for x in rows: f.write(json.dumps(x) + '\n')
    f.write(json.dumps({'type': 'summary', 'run_id': run_id,
                        'cases': len(rows), 'fails': len(fails)}) + '\n')
line = f"cases: {len(rows)} fails: {len(fails)}"
print(line if quiet else line + '\n' + '\n'.join(
    'FAIL: ' + json.dumps(x) for x in fails))
sys.exit(1 if fails else 0)
