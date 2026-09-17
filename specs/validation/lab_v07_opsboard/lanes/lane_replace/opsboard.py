from __future__ import annotations
import csv,hashlib,json,sqlite3,time
from io import StringIO

LEAK_SECRET=False
SAME_CHANNEL_DELIVERED=True
BYPASS_CAPS=False
BROKEN_AUDIT=False

class OpsBoard:
    MAX_SENDS=3
    MAX_SPEND=0.50
    def __init__(self,db_path,provider_db):
        self.db_path=str(db_path); self.provider_db=str(provider_db); self._init()
    def db(self): return sqlite3.connect(self.db_path)
    def provider(self): return sqlite3.connect(self.provider_db)
    def _init(self):
        with self.db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'NEW');
            CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,lead_id INTEGER NOT NULL,campaign_id TEXT NOT NULL,status TEXT NOT NULL,cost REAL NOT NULL,idempotency_key TEXT UNIQUE NOT NULL,provider_message_id TEXT);
            CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL,event_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS debug(k TEXT PRIMARY KEY,v TEXT NOT NULL);
            """)
        with self.provider() as c:
            c.execute('CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,job_id INTEGER NOT NULL,email TEXT NOT NULL,created_at REAL NOT NULL)')
    def _audit(self,kind,payload):
        event=json.dumps({'kind':kind,'payload':payload},sort_keys=True,separators=(',',':'))
        with self.db() as c:
            row=c.execute('SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone(); prev=row[0] if row else '0'*64
            h=hashlib.sha256((('bad' if BROKEN_AUDIT else prev)+event).encode()).hexdigest()
            c.execute('INSERT INTO audit(prev_hash,event_hash,event_json) VALUES(?,?,?)',(prev,h,event))
    def verify_audit(self):
        prev='0'*64
        with self.db() as c: rows=c.execute('SELECT prev_hash,event_hash,event_json FROM audit ORDER BY seq').fetchall()
        for p,h,e in rows:
            if p!=prev:return False
            if hashlib.sha256((prev+e).encode()).hexdigest()!=h:return False
            prev=h
        return True
    def import_csv(self,text):
        n=0
        for r in csv.DictReader(StringIO(text)):
            email=(r.get('email') or '').strip().lower(); name=(r.get('name') or '').strip()
            if not email: continue
            with self.db() as c:
                before=c.total_changes; c.execute('INSERT OR IGNORE INTO leads(email,name) VALUES(?,?)',(email,name)); n+=c.total_changes-before
        self._audit('import_csv',{'inserted':n}); return n
    def leads(self):
        with self.db() as c:return c.execute('SELECT id,email,name,status FROM leads ORDER BY id').fetchall()
    def set_default_view(self,v):
        if v not in {'compact','detailed'}:raise ValueError('bad-view')
        with self.db() as c:c.execute("INSERT INTO settings(k,v) VALUES('default_view',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(v,))
        self._audit('preference',{'default_view':v})
    def default_view(self):
        with self.db() as c:
            r=c.execute("SELECT v FROM settings WHERE k='default_view'").fetchone(); return r[0] if r else 'compact'
    def create_job(self,lead_id,campaign_id,key,cost=0.10):
        with self.db() as c:
            r=c.execute('SELECT id FROM jobs WHERE idempotency_key=?',(key,)).fetchone()
            if r:return r[0]
            cur=c.execute("INSERT INTO jobs(lead_id,campaign_id,status,cost,idempotency_key) VALUES(?,?,'PENDING',?,?)",(lead_id,campaign_id,float(cost),key)); jid=cur.lastrowid
        self._audit('create_job',{'job_id':jid,'campaign_id':campaign_id}); return jid
    def _campaign_usage(self,campaign_id):
        with self.db() as c:
            r=c.execute("SELECT COUNT(*),COALESCE(SUM(cost),0) FROM jobs WHERE campaign_id=? AND status IN ('SENT_UNVERIFIED','DELIVERED')",(campaign_id,)).fetchone(); return int(r[0]),float(r[1])
    def dispatch(self,job_id,provider_secret,authority):
        if not authority or not authority.get('signature'):raise PermissionError('qp-authority-required')
        with self.db() as c:r=c.execute('SELECT campaign_id,cost,lead_id,status FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not r:raise KeyError(job_id)
        campaign,cost,lead_id,status=r
        if status in ('SENT_UNVERIFIED','DELIVERED'):return status
        sends,spent=self._campaign_usage(campaign)
        if not BYPASS_CAPS and (sends>=self.MAX_SENDS or spent+cost>self.MAX_SPEND+1e-12):raise PermissionError('campaign-cap')
        with self.db() as c:email=c.execute('SELECT email FROM leads WHERE id=?',(lead_id,)).fetchone()[0]
        if LEAK_SECRET:
            with self.db() as c:c.execute("INSERT OR REPLACE INTO debug(k,v) VALUES('provider_secret',?)",(provider_secret,))
        msg='msg:'+hashlib.sha256(f'{job_id}|{email}|{time.time_ns()}'.encode()).hexdigest()[:20]
        with self.provider() as c:c.execute('INSERT INTO messages(id,job_id,email,created_at) VALUES(?,?,?,?)',(msg,job_id,email,time.time()))
        next_status='DELIVERED' if SAME_CHANNEL_DELIVERED else 'SENT_UNVERIFIED'
        with self.db() as c:c.execute('UPDATE jobs SET status=?,provider_message_id=? WHERE id=?',(next_status,msg,job_id))
        self._audit('dispatch',{'job_id':job_id,'provider_message_id':msg,'status':next_status}); return next_status
    def readback(self,job_id):
        with self.provider() as p:r=p.execute('SELECT id FROM messages WHERE job_id=?',(job_id,)).fetchone()
        if not r:return False
        with self.db() as c:c.execute("UPDATE jobs SET status='DELIVERED' WHERE id=?",(job_id,))
        self._audit('independent_readback',{'job_id':job_id,'provider_message_id':r[0]}); return True
    def job(self,jid):
        with self.db() as c:return c.execute('SELECT id,lead_id,campaign_id,status,cost,idempotency_key,provider_message_id FROM jobs WHERE id=?',(jid,)).fetchone()
    def metrics(self):
        with self.db() as c:
            leads=c.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
            pending=c.execute("SELECT COUNT(*) FROM jobs WHERE status='PENDING'").fetchone()[0]
            delivered=c.execute("SELECT COUNT(*) FROM jobs WHERE status='DELIVERED'").fetchone()[0]
            spent=c.execute("SELECT COALESCE(SUM(cost),0) FROM jobs WHERE status IN ('SENT_UNVERIFIED','DELIVERED')").fetchone()[0]
        return {'leads':leads,'pending_jobs':pending,'delivered_jobs':delivered,'spend_used':float(spent),'default_view':self.default_view()}
    def contains_secret(self,secret):
        with self.db() as c:
            for table in ('leads','jobs','settings','audit','debug'):
                for row in c.execute(f'SELECT * FROM {table}').fetchall():
                    if secret in json.dumps(row):return True
        return False
