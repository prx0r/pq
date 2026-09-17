from __future__ import annotations
from dataclasses import dataclass
from .processor_calculus import canonical_recipe,compose_budget

@dataclass(frozen=True)
class ProcessorLane:
    id:str; contract_root:str; policy:str; processor_ids:tuple[str,...]; estimated_cost:object; mutation:str=''

class ProcessorAssembler:
    """Create five diverse, *type-valid* processor graphs under one ContractRoot.

    The assembler may mutate processor order/composition, but it may never emit a
    graph whose declared requirements cannot be satisfied by prior outputs plus
    the initial kernel inputs. Budget trimming is also validity-preserving.
    """
    def __init__(self,registry): self.registry=registry

    def _valid(self,ids):
        try: self.registry.validate_graph(tuple(ids)); return True
        except Exception: return False

    def _dedup(self,ids): return list(dict.fromkeys(x for x in ids if x in self.registry.ids()))

    def _fit(self,ids,budget):
        xs=self._dedup(ids)
        if not self._valid(xs): raise ValueError(f'invalid processor graph: {xs}')
        if compose_budget(self.registry,xs).within(budget): return tuple(xs)
        protected={'proof.construct','proof.verify'}
        # Prefer removing expensive/experimental search components, but only if
        # the complete resulting graph remains type-valid.
        order=sorted((x for x in xs if x not in protected), key=lambda x:(
            self.registry.get(x).cost.money_minor,
            self.registry.get(x).cost.tokens,
            self.registry.get(x).cost.wall_ms,
        ), reverse=True)
        for victim in order:
            if compose_budget(self.registry,xs).within(budget): break
            trial=list(xs); trial.remove(victim)
            if self._valid(trial): xs=trial
        if not compose_budget(self.registry,xs).within(budget):
            raise RuntimeError('no type-valid processor lane fits budget')
        return tuple(xs)

    def _insert_before(self,base,marker,extras):
        xs=list(base); i=xs.index(marker) if marker in xs else len(xs)
        return xs[:i]+[x for x in extras if x in self.registry.ids() and x not in xs]+xs[i:]

    def _candidate_available_before_proof(self,base):
        xs=list(base); i=xs.index('proof.construct') if 'proof.construct' in xs else len(xs)
        try: available=self.registry.validate_graph(xs[:i])
        except Exception: return False
        return 'candidate_artifact' in available

    def lanes(self,contract_root,proof_types,*,budget,history_best=()):
        base=[]
        for pt in proof_types:
            for pid in canonical_recipe(pt):
                if pid not in base and pid in self.registry.ids(): base.append(pid)
        if history_best:
            exploit=[x for x in history_best if x in self.registry.ids()]
            for x in base:
                if x not in exploit: exploit.append(x)
        else: exploit=list(base)
        # A history prefix can be stale/incompatible with the new proof type.
        # Fall back to the canonical composition rather than emitting an invalid lane.
        if not self._valid(exploit): exploit=list(base)

        direct=self._fit(exploit,budget)

        # Mutation/falsification occurs before final tests/proof construction.
        mutate=list(exploit)
        insert_marker='test.hidden' if 'test.hidden' in mutate else 'proof.construct'
        mutate=self._insert_before(mutate,insert_marker,('redteam.falsify',))
        # Repair only makes semantic/type sense when a candidate artifact already exists.
        if self._candidate_available_before_proof(mutate):
            mutate=self._insert_before(mutate,insert_marker,('repair.failure',))
        mutate=self._fit(mutate,budget)

        # Forced novel family is itself a canonical, valid exploration proof route.
        explore=list(canonical_recipe('exploration'))
        explore=self._fit(explore,budget)

        # Underengineer by greedily deleting expensive processors only when the
        # whole graph remains valid; never delete dependencies blindly.
        cheap=list(exploit)
        expensive=('harbor.rollout','harbor.evaluate','cg.evolve','web.search','module.design','actuality.independent_readback')
        for victim in expensive:
            if victim in cheap:
                trial=list(cheap); trial.remove(victim)
                if self._valid(trial): cheap=trial
        cheap=self._fit(cheap,budget)

        # Robust lane adds falsification and, for artifact-producing tasks,
        # independent evaluation/readback before proof construction.
        robust=list(exploit)
        extras=['redteam.falsify']
        if self._candidate_available_before_proof(robust): extras += ['harbor.evaluate','actuality.independent_readback']
        robust=self._insert_before(robust,'proof.construct',extras)
        robust=self._fit(robust,budget)

        defs=[
            ('exploit',direct,''),
            ('mutate',mutate,'falsify/repair before verification'),
            ('explore',explore,'forced novel family'),
            ('underengineer',cheap,'minimum valid graph'),
            ('robust',robust,'extra falsification/evaluation'),
        ]
        lanes=[]; seen=set()
        for i,(policy,ids,mutation) in enumerate(defs,1):
            ids=tuple(ids)
            if ids in seen:
                # Add a harmless, type-valid diversity processor before proof.
                alt=self._insert_before(ids,'proof.construct',('ensemble.vote',))
                if self._valid(alt) and compose_budget(self.registry,alt).within(budget): ids=tuple(alt)
            seen.add(ids)
            # Final constitutional assertion: assembler never emits invalid graphs.
            self.registry.validate_graph(ids)
            lanes.append(ProcessorLane(f'lane-{i}',contract_root,policy,ids,compose_budget(self.registry,ids),mutation))
        return tuple(lanes)
