from __future__ import annotations
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,time,os
from typing import Any
from .human import KEYS,HumanTask,HumanDecisionLearner,ContinualHumanController,AutonomyStage
from .payloads import HumanPayloadStore,PayloadRef

class WorkbenchState:
    """Small local controller. Raw human payloads never appear in snapshot/logs/learner state."""
    def __init__(self,state_dir:str|Path|None=None,learner:HumanDecisionLearner|None=None):
        self.state_dir=Path(state_dir or os.environ.get("AGENTCOM_STATE_DIR",Path.home()/".agentcom-workbench"))
        self.state_dir.mkdir(parents=True,exist_ok=True)
        self.policy_path=self.state_dir/"human_policy.json"
        self.payload_store=HumanPayloadStore(self.state_dir/"payloads")
        self.learner=learner or HumanDecisionLearner.load(self.policy_path)
        self.controller=ContinualHumanController(self.learner)
        self.human_tasks:list[dict[str,Any]]=[]
        self._task_runtime:dict[str,dict[str,Any]]={}
        self.logs:list[dict[str,Any]]=[]
        self.runs:list[dict[str,Any]]=[]
        self.wallet:list[dict[str,Any]]=[]
        self.last_key:int|None=None
        self.inputs:list[dict[str,Any]]=[]  # metadata only; no raw text

    def snapshot(self):
        return {
            "human_tasks":self.human_tasks,
            "logs":self.logs[-200:],
            "runs":self.runs,
            "wallet":self.wallet,
            "last_key":self.last_key,
            "inputs":self.inputs[-50:],
            "learning":{"metrics":self.learner.metrics(),"macros":self.learner.macro_candidates(3)[:10]},
        }

    def present_task(self,task:HumanTask,state:dict[str,Any])->dict[str,Any]:
        task.validate()
        pred,auto=self.controller.predict(task,state)
        view={
            "id":task.id,"project":task.project,"class":task.cls.value,"summary":task.summary,
            "options":list(task.options),"recommendation":task.recommendation,"cost_of_wait":task.cost_of_wait,
            "risk":task.risk,"needed_from":task.needed_from,"readiness_check":task.readiness_check,
            "presented_at":time.time(),
            # Prediction intentionally hidden from the human-facing view.
            "learning":{"support":pred.support,"ood":pred.ood,"stage":auto.stage.value,"progress":auto.progress,"eligible":auto.eligible},
        }
        self._task_runtime[task.id]={"task":task,"state":dict(state),"prediction_id":pred.id,"presented_at":view["presented_at"]}
        self.human_tasks=[x for x in self.human_tasks if x.get("id")!=task.id]+[view]
        self.logs.append({"t":time.time(),"kind":"human-task-presented","task_id":task.id,"class":task.cls.value})
        return view


    def present_or_auto(self,task:HumanTask,state:dict[str,Any])->dict[str,Any]:
        """Return an autonomous local choice only after earned policy evidence; otherwise queue a human task."""
        task.validate();pred,auto=self.controller.predict(task,state)
        if auto.stage==AutonomyStage.AUTO_LOCAL and not auto.hard_human:
            self.learner.pending.pop(pred.id,None)
            self.logs.append({"t":time.time(),"kind":"autonomy-local","task_id":task.id,"key":pred.key,"support":pred.support,"progress":auto.progress})
            return {"mode":"AUTO_LOCAL","key":pred.key,"prediction_id":pred.id,"progress":auto.progress,"authority":False}
        # Reuse the already generated prediction rather than contaminating history with a second prediction.
        view={"id":task.id,"project":task.project,"class":task.cls.value,"summary":task.summary,"options":list(task.options),"recommendation":task.recommendation,"cost_of_wait":task.cost_of_wait,"risk":task.risk,"needed_from":task.needed_from,"readiness_check":task.readiness_check,"presented_at":time.time(),"learning":{"support":pred.support,"ood":pred.ood,"stage":auto.stage.value,"progress":auto.progress,"eligible":auto.eligible}}
        self._task_runtime[task.id]={"task":task,"state":dict(state),"prediction_id":pred.id,"presented_at":view["presented_at"]};self.human_tasks=[x for x in self.human_tasks if x.get("id")!=task.id]+[view];self.logs.append({"t":time.time(),"kind":"human-task-presented","task_id":task.id,"class":task.cls.value});return {"mode":"HUMAN","task":view,"authority":False}

    def _active_task_id(self)->str|None:
        return self.human_tasks[0]["id"] if self.human_tasks else None

    def submit_payload(self,task_id:str,kind:str,text:str)->dict[str,Any]:
        if task_id not in self._task_runtime:raise KeyError("unknown-human-task")
        ref=self.payload_store.put(task_id,kind,text)
        pub=HumanPayloadStore.public(ref)
        self.inputs.append(pub)
        self.logs.append({"t":time.time(),"kind":"human-payload","task_id":task_id,"payload_id":ref.id,"sha256":ref.sha256,"bytes":ref.bytes,"payload_kind":kind})
        return pub

    def press_key(self,task_id:str,key:int,human_seconds:float=0.2,payload_id:str|None=None)->dict[str,Any]:
        if key not in KEYS:raise ValueError("key-0-9")
        rt=self._task_runtime.get(task_id)
        if not rt:raise KeyError("unknown-human-task")
        payload_sha=None
        if payload_id:
            meta=next((x for x in reversed(self.inputs) if x.get("id")==payload_id and x.get("task_id")==task_id),None)
            if not meta:raise ValueError("payload-ref-not-for-task")
            payload_sha=meta["sha256"]
        ev=self.controller.observe(rt["prediction_id"],rt["task"],rt["state"],key,float(human_seconds),payload_sha256=payload_sha)
        self.learner.save(self.policy_path)
        self.last_key=key
        self.logs.append({"t":time.time(),"kind":"human-key","task_id":task_id,"key":key,"semantic":KEYS[key],"prediction_id":ev.prediction_id,"payload_sha256":payload_sha})
        # The key resolves the interaction record, not necessarily external authority.
        self.human_tasks=[x for x in self.human_tasks if x.get("id")!=task_id]
        self._task_runtime.pop(task_id,None)
        return {"ok":True,"semantic":KEYS[key],"prediction_id":ev.prediction_id,"authority":False}

    def add_run(self,run:dict[str,Any])->dict[str,Any]:
        row=dict(run);row.setdefault("status","PROPOSED");self.runs=[r for r in self.runs if r.get("id")!=row.get("id")]+[row];return row

    def decide_run(self,run_id:str,decision:str)->dict[str,Any]:
        row=next((r for r in self.runs if r.get("id")==run_id),None)
        if not row:raise KeyError("unknown-run")
        d=decision.lower()
        if d in {"approve","5"}:
            row["status"]="HUMAN_APPROVED_PENDING_QP"
            row["human_approved_at"]=time.time()
        elif d in {"deny","6"}:
            row["status"]="DENIED_REPLAN";row["human_denied_at"]=time.time()
        else:raise ValueError("run-decision-must-approve-or-deny")
        self.logs.append({"t":time.time(),"kind":"run-decision","run_id":run_id,"decision":d,"status":row["status"]})
        return row

    def mark_qp_authorized(self,run_id:str,grant_ref:str)->dict[str,Any]:
        row=next((r for r in self.runs if r.get("id")==run_id),None)
        if not row:raise KeyError("unknown-run")
        if row.get("status")!="HUMAN_APPROVED_PENDING_QP":raise PermissionError("human-approval-required-before-qp-link")
        row["status"]="QP_AUTHORIZED";row["grant_ref"]=grant_ref
        self.logs.append({"t":time.time(),"kind":"qp-authority-linked","run_id":run_id,"grant_ref":grant_ref})
        return row

STATE=WorkbenchState()

def make_handler(root:Path,state:WorkbenchState=STATE):
    class Handler(BaseHTTPRequestHandler):
        def _json(self,obj,code=200):
            b=json.dumps(obj,default=str).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
        def _body(self):
            n=int(self.headers.get("Content-Length","0"));return json.loads(self.rfile.read(n) or b"{}")
        def do_GET(self):
            if self.path=="/api/state":return self._json(state.snapshot())
            p=(root/("index.html" if self.path in ("/","") else self.path.lstrip("/"))).resolve()
            if root.resolve() not in p.parents and p!=root.resolve():return self.send_error(403)
            if not p.exists():return self.send_error(404)
            typ="text/html" if p.suffix==".html" else "text/javascript" if p.suffix==".js" else "text/css" if p.suffix==".css" else "application/manifest+json" if p.suffix==".webmanifest" else "application/json"
            b=p.read_bytes();self.send_response(200);self.send_header("Content-Type",typ);self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
        def do_POST(self):
            try:data=self._body()
            except Exception:return self._json({"ok":False,"error":"bad-json"},400)
            try:
                if self.path=="/api/key":
                    task_id=str(data.get("task_id") or state._active_task_id() or "")
                    if not task_id:return self._json({"ok":False,"error":"no-active-human-task"},409)
                    return self._json(state.press_key(task_id,int(data["key"]),float(data.get("human_seconds",0.2)),data.get("payload_id")))
                if self.path=="/api/input":
                    task_id=str(data.get("task_id") or state._active_task_id() or "")
                    if not task_id:return self._json({"ok":False,"error":"no-active-human-task"},409)
                    kind=str(data.get("kind","text"));return self._json({"ok":True,"payload":state.submit_payload(task_id,kind,str(data.get("text","")))})
                if self.path=="/api/run-decision":
                    return self._json({"ok":True,"run":state.decide_run(str(data["run_id"]),str(data["decision"]))})
                return self._json({"ok":False,"error":"unknown-endpoint"},404)
            except (ValueError,KeyError,PermissionError) as e:
                return self._json({"ok":False,"error":str(e)},400)
        def log_message(self,*args):pass
    return Handler

def serve(host:str|None=None,port:int|None=None,root:Path|None=None):
    host=host or os.environ.get("AGENTCOM_WORKBENCH_HOST","127.0.0.1")
    port=int(port or os.environ.get("AGENTCOM_WORKBENCH_PORT","8765"))
    root=root or (Path(__file__).resolve().parent/"data"/"workbench")
    if host not in {"127.0.0.1","localhost","::1"}:
        print("WARNING: reference Workbench has no production auth/TLS; expose only on a trusted LAN/VPN")
    srv=ThreadingHTTPServer((host,port),make_handler(root));print(f"AgentCom Workbench http://{host}:{port}");srv.serve_forever()
