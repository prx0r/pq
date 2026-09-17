from __future__ import annotations
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib

class TestTier(str, Enum):
    T0_DISTRIBUTION='T0_DISTRIBUTION'
    T1_SPEC='T1_SPEC'
    T2_PROOF='T2_PROOF'
    T3_PROCESSOR='T3_PROCESSOR'
    T4_BUILD='T4_BUILD'
    T5_ACTUALITY='T5_ACTUALITY'
    T6_HUMAN='T6_HUMAN'
    T7_AUTHORITY='T7_AUTHORITY'
    T8_ECONOMICS='T8_ECONOMICS'
    T9_TOURNAMENT='T9_TOURNAMENT'
    T10_LEARNING='T10_LEARNING'
    T11_ADVERSARIAL='T11_ADVERSARIAL'
    T12_HISTORICAL='T12_HISTORICAL'
    T13_FRESH_RELEASE='T13_FRESH_RELEASE'

TestTier.__test__ = False

@dataclass
class ValidationRecord:
    id:str
    tier:TestTier
    hypothesis:str
    expected:str
    status:str='PENDING'
    observed:object=None
    action:str=''
    evidence:list[str]=field(default_factory=list)
    started_at:str=''
    ended_at:str=''

class ValidationJournal:
    def __init__(self,name:str,outdir:str|Path):
        self.name=name;self.outdir=Path(outdir);self.outdir.mkdir(parents=True,exist_ok=True);self.records=[]
    def run(self,id:str,tier:TestTier,hypothesis:str,expected:str,fn,action_on_fail:str=''):
        r=ValidationRecord(id,tier,hypothesis,expected,started_at=datetime.now(timezone.utc).isoformat())
        try:
            obs=fn(); ok=bool(obs.get('ok')) if isinstance(obs,dict) and 'ok' in obs else bool(obs)
            r.observed=obs;r.status='PASS' if ok else 'FAIL'
            if not ok:r.action=action_on_fail
        except Exception as e:
            r.status='FAIL';r.observed={'exception':repr(e)};r.action=action_on_fail
        r.ended_at=datetime.now(timezone.utc).isoformat();self.records.append(r);self.flush();return r
    def add(self,r:ValidationRecord):self.records.append(r);self.flush()
    def flush(self):
        payload={'schema':'agentcom.validation-journal/0.1','name':self.name,'records':[asdict(x) for x in self.records]}
        raw=json.dumps(payload,indent=2,sort_keys=True,default=str);(self.outdir/'journal.json').write_text(raw)
        md=[f'# {self.name}\n']
        for i,x in enumerate(self.records,1):
            md += [f'## {i}. {x.id} — {x.status}\n',f'**Tier:** `{x.tier.value}`\n',f'**Hypothesis:** {x.hypothesis}\n',f'**Expected:** {x.expected}\n','**Observed:**\n```json\n'+json.dumps(x.observed,indent=2,default=str)+'\n```\n',f'**Action:** {x.action or "none"}\n']
        (self.outdir/'JOURNAL.md').write_text('\n'.join(md))
    def summary(self):
        passed=sum(x.status=='PASS' for x in self.records);failed=sum(x.status=='FAIL' for x in self.records)
        return {'name':self.name,'total':len(self.records),'passed':passed,'failed':failed,'ok':failed==0,'journal_sha256':hashlib.sha256((self.outdir/'journal.json').read_bytes()).hexdigest()}
