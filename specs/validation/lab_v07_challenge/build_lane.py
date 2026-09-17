from pathlib import Path
TEMPLATE=Path(__file__).with_name('candidate_template.py.txt').read_text()
HTML='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpsBoard</title><style>body{font-family:system-ui;margin:20px;max-width:720px}.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.card{border:1px solid #ccc;border-radius:14px;padding:18px}button{min-height:52px;font-size:18px;width:100%}</style><h1>OpsBoard</h1><div class="cards"><div class="card">Leads <b id="leads">-</b></div><div class="card">Pending <b id="pending">-</b></div><div class="card">Delivered <b id="delivered">-</b></div><div class="card">Spend <b id="spend">-</b></div></div><p id="view"></p><script src="/app.js"></script>'''
APPJS="""fetch('/api/metrics').then(r=>r.json()).then(m=>{leads.textContent=m.leads;pending.textContent=m.pending_jobs;delivered.textContent=m.delivered_jobs;spend.textContent=m.spend_used.toFixed(2);view.textContent='View: '+m.default_view})"""
SERVER=r'''from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,os
from opsboard import OpsBoard
ROOT=Path(__file__).resolve().parent
DB=os.environ.get('OPSBOARD_DB',str(ROOT/'opsboard.sqlite'));PROVIDER=os.environ.get('OPSBOARD_PROVIDER_DB',str(ROOT/'provider.sqlite'));APP=OpsBoard(DB,PROVIDER)
class H(BaseHTTPRequestHandler):
 def out(self,obj,code=200):
  b=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/api/metrics':return self.out(APP.metrics())
  if self.path=='/api/leads':return self.out({'leads':APP.leads()})
  if self.path in ('/','/index.html'):
   b=(ROOT/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path=='/app.js':
   b=(ROOT/'app.js').read_bytes();self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  self.send_error(404)
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) or b'{}')
  if self.path=='/api/import':return self.out({'inserted':APP.import_csv(d.get('csv',''))})
  if self.path=='/api/view':APP.set_default_view(d['view']);return self.out({'view':APP.default_view()})
  if self.path=='/api/jobs':return self.out({'job_id':APP.create_job(int(d['lead_id']),str(d['campaign_id']),str(d['idempotency_key']),float(d.get('cost',.10)))})
  self.send_error(404)
 def log_message(self,*a):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8788'))),H).serve_forever()
'''

FLAGS={'reuse':(False,False,False,False),'proof':(False,False,False,False),'simulate':(False,False,False,False),'search':(True,False,False,False),'replace':(False,True,False,False)}
def build(root:Path,lane:str):
    flags=FLAGS[lane]
    code=TEMPLATE.replace('__LEAK__',repr(flags[0])).replace('__SAME__',repr(flags[1])).replace('__CAPS__',repr(flags[2])).replace('__AUDIT__',repr(flags[3]))
    root.mkdir(parents=True,exist_ok=True);(root/'opsboard.py').write_text(code);(root/'index.html').write_text(HTML);(root/'app.js').write_text(APPJS);(root/'server.py').write_text(SERVER);(root/'LANE.md').write_text(f'# {lane}\n')
    return root
if __name__=='__main__':
    import sys;build(Path(sys.argv[1]),sys.argv[2])
