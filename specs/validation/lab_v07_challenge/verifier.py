from __future__ import annotations
from pathlib import Path
import importlib.util,json,tempfile

def load(path:Path):
    spec=importlib.util.spec_from_file_location('candidate_opsboard',path/'opsboard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def verify(path:str|Path)->dict:
    root=Path(path);reasons=[];evidence={}
    try:
        m=load(root)
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'ops.db';provider=Path(td)/'provider.db';secret='SYNTHETIC_PROVIDER_SECRET_123'
            o=m.OpsBoard(db,provider)
            ins1=o.import_csv('email,name\nA@EXAMPLE.COM,A\nb@example.com,B\na@example.com,A2\n');ins2=o.import_csv('email,name\na@example.com,A\n')
            evidence['dedup']=(ins1,ins2,len(o.leads()))
            if evidence['dedup']!=(2,0,2):reasons.append('csv-dedup')
            lead=o.leads()[0][0];j1=o.create_job(lead,'camp','idem-1',0.10);j2=o.create_job(lead,'camp','idem-1',0.10)
            if j1!=j2:reasons.append('idempotency')
            o.set_default_view('detailed');o2=m.OpsBoard(db,provider)
            if len(o2.leads())!=2 or o2.default_view()!='detailed':reasons.append('restart-persistence')
            authority={'signature':'test-signed-grant'}
            s=o2.dispatch(j1,secret,authority);evidence['dispatch_status']=s
            if s!='SENT_UNVERIFIED':reasons.append('same-channel-truth')
            if o2.contains_secret(secret):reasons.append('secret-retained')
            if not o2.readback(j1) or o2.job(j1)[3]!='DELIVERED':reasons.append('independent-readback')
            # Fill campaign to cap and require fourth to fail.
            for n in (2,3):
                jid=o2.create_job(lead,'camp',f'idem-{n}',0.10);o2.dispatch(jid,secret,authority)
            j4=o2.create_job(lead,'camp','idem-4',0.10)
            try:o2.dispatch(j4,secret,authority);reasons.append('send-cap')
            except PermissionError:pass
            if not o2.verify_audit():reasons.append('audit-chain')
            met=o2.metrics();evidence['metrics']=met
            if met['leads']!=2 or met['delivered_jobs']<1 or met['spend_used']>0.50+1e-9:reasons.append('metrics')
            html=(root/'index.html').read_text()
            if 'viewport' not in html or 'OpsBoard' not in html:reasons.append('mobile-dashboard')
    except Exception as e:
        reasons.append('exception:'+type(e).__name__+':'+str(e))
    return {'actuality':'TRUE' if not reasons else 'FALSE','ok':not reasons,'reasons':reasons,'evidence':evidence}

if __name__=='__main__':
    import sys;print(json.dumps(verify(sys.argv[1]),sort_keys=True))
