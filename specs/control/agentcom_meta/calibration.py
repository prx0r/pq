from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Any


def wilson_upper(failures:int,total:int,z:float=1.96)->float:
    """One-sided-ish conservative upper bound using the Wilson interval upper edge.

    We use it as an operational risk bound, not as a proof of a population parameter.
    """
    if total <= 0:
        return 1.0
    p=failures/total
    den=1.0+z*z/total
    center=(p+z*z/(2*total))/den
    half=z*sqrt((p*(1-p)/total)+(z*z/(4*total*total)))/den
    return min(1.0,max(0.0,center+half))


def expected_calibration_error(rows:Iterable[tuple[float,int]],bins:int=10)->float:
    data=[(min(max(float(p),0.0),1.0),int(y)) for p,y in rows]
    if not data:return 1.0
    groups=[[] for _ in range(max(1,bins))]
    for p,y in data:
        i=min(len(groups)-1,int(p*len(groups)))
        groups[i].append((p,y))
    n=len(data);ece=0.0
    for g in groups:
        if not g:continue
        mp=sum(p for p,_ in g)/len(g);my=sum(y for _,y in g)/len(g)
        ece += len(g)/n*abs(mp-my)
    return ece

@dataclass(frozen=True)
class CalibrationReport:
    n:int
    accuracy:float
    brier:float
    ece:float
    verified_n:int
    verified_failures:int
    verified_failure_rate:float
    verified_failure_upper:float


def report(events:Iterable[Any])->CalibrationReport:
    xs=list(events);n=len(xs)
    if not xs:
        return CalibrationReport(0,0.0,1.0,1.0,0,0,1.0,1.0)
    acc=sum(bool(e.correct) for e in xs)/n
    brier=sum((float(e.predicted_p)-(1.0 if e.correct else 0.0))**2 for e in xs)/n
    ece=expected_calibration_error((float(e.predicted_p),1 if e.correct else 0) for e in xs)
    verified=[e for e in xs if e.outcome_verified is not None]
    failures=sum(1 for e in verified if e.outcome_verified is False)
    vn=len(verified);rate=failures/vn if vn else 1.0
    return CalibrationReport(n,acc,brier,ece,vn,failures,rate,wilson_upper(failures,vn))
