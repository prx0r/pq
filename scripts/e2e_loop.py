#!/usr/bin/env python3
"""E2E autonomy loop: daemon -> persisted queue -> dashboard -> human press.
No model calls (spend-free). Logs runs/e2e-loop.jsonl.
Usage: e2e_loop.py  (env: DASH_PORT default 8799)
Backend note: the human press here is scripted; live-model judgment calls
go through live.sh on PQ_MODEL (muse-spark-1.3-contributor, hardcoded).
"""
import json, os, subprocess, sys, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RUNS = os.path.join(ROOT, 'runs')
HFILE = os.path.join(RUNS, 'htasks.json')
LOG = os.path.join(RUNS, 'e2e-loop.jsonl')
TOKEN = 'e2e-token'
PORT = os.environ.get('DASH_PORT', '8799')
run_id = 'e2e-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime())
rows = []
def rec(step, data):
    rows.append({'ts': int(time.time()), 'run_id': run_id, 'step': step,
                 'data': data})

from agentcom.services.daemon import Daemon
from agentcom.htasks.queue import HQueue, HTask
d = Daemon(os.path.join(RUNS, 'daemon-journal.jsonl'))
def emit_htask(job):
    q = HQueue.load(HFILE)
    q.emit(HTask('e2e-digit-1', 'digit',
                 'Autonomy loop live. Press 7 to confirm the human is in the loop.',
                 prediction='7', confidence=0.9, lease_s=600,
                 campaign='demo', lane='e2e'))
    q.save(HFILE)
    return {'emitted': 'e2e-digit-1'}
job = d.submit({'kind': 'htask-emit', 'campaign': 'demo'})
out = d.tick(emit_htask)
rec('daemon-emit', {'job': out['job_id'], 'state': out['state'],
                    'result': out.get('result')})

env = dict(os.environ, DASH_TOKEN=TOKEN, DASH_PORT=PORT)
srv = subprocess.Popen([sys.executable, 'dashboard/server.py'], cwd=ROOT,
                       env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
time.sleep(1.5)
def api(path, body=None):
    url = f'http://127.0.0.1:{PORT}{path}?token={TOKEN}'
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data,
        headers={'Content-Type': 'application/json'},
        method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())
try:
    tasks = api('/api/tasks')
    mine = [t for t in tasks if t['task_id'] == 'e2e-digit-1']
    rec('poll-tasks', {'count': len(tasks),
                       'mine': mine[0]['state'] if mine else None})
    tiles = api('/api/tiles')
    rec('tiles', {'counts': tiles['counts'],
                  'htask_tiles': [t for t in tiles['tiles']
                                  if t['kind'] == 'htask']})
    ans = api('/api/answer', {'task_id': 'e2e-digit-1', 'value': '7'})
    rec('human-press-7', ans)
    cal = api('/api/calibration')
    rec('calibration', cal)
    tiles2 = api('/api/tiles')
    rec('tiles-after', {'counts': tiles2['counts']})
finally:
    srv.terminate()

ok = (out['state'] == 'done'
      and mine and mine[0]['state'] == 'displayed'
      and ans.get('ok') and ans.get('hit') is True
      and tiles['counts']['approval'] >= 1
      and tiles2['counts']['approval'] == 0
      and cal['scored'] >= 1)
rec('verdict', {'autonomy_loop': 'WORKING' if ok else 'BROKEN'})
with open(LOG, 'a') as f:
    for r in rows: f.write(json.dumps(r) + '\n')
print('E2E:', 'WORKING' if ok else 'BROKEN')
sys.exit(0 if ok else 1)
