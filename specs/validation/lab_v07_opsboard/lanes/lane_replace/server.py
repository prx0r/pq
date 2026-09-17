from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
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
