"""Deterministic persisted session/Job reconciliation with index readiness gating."""
import asyncio

from foundry_v2.roles.registry import Role


class Lifecycle:
    def __init__(self,store,deployment,preflight,clock):
        self.store,self.deployment,self.preflight,self.clock=store,deployment,preflight,clock

    async def reconcile(self,evaluation):
        snapshot=await self.store.snapshot(evaluation)
        config=snapshot['configuration']; fleet=config['fleet']; state=snapshot['state']
        if state=='configured': return
        if state=='preflight':
            result=await self.preflight.run(config)
            await self.store.preflight_result(evaluation,result)
            if not result['passed']: return
            await self.store.state(evaluation,'indexing')
            snapshot=await self.store.snapshot(evaluation); state=snapshot['state']
        jobs=await self.deployment.list_jobs(evaluation)
        if state in ('stopped','failed'):
            for session in snapshot['sessions']:
                if any(j['session_id']==session['session_id'] for j in jobs): await self.deployment.stop_job(session)
            return
        if snapshot.get('restart_requested'):
            live=[s for s in snapshot['sessions'] if s['state'] in ('registered','running','draining')]
            if live:
                for session in live:
                    await self.store.wrap_up(session)
                    if self.clock.utc()>=session.get('drain_deadline',float('inf')): await self.deployment.stop_job(session)
                return
            await self.store.restart(evaluation)
            return
        desired={'indexer':fleet['counts']['indexer']}
        if snapshot['index_queryable'] and state not in ('draining','stopped'):
            desired=dict(fleet['counts']); desired['orchestrator']=1
            if state=='indexing': await self.store.state(evaluation,'running')
        if state=='draining':
            desired={}
            if not any(s['state'] in ('registered','running','draining') for s in snapshot['sessions']):
                await self.store.state(evaluation,'stopped')
                return
        sessions=snapshot['sessions']
        for session in sessions:
            if session['state'] in ('registered','running','draining') and session['slot']>=desired.get(session['role'],0):
                await self.store.wrap_up(session)
                if self.clock.utc()>=session.get('drain_deadline',float('inf')):
                    await self.deployment.stop_job(session)
                # Rotation/drain never steals claims; receipt-clock reaper does that.
        for role,count in desired.items():
            Role(role)
            for slot in range(count):
                live=next((s for s in sessions if s['role']==role and s['slot']==slot and s['state'] in ('registered','running','draining')),None)
                if live:
                    if not any(j['session_id']==live['session_id'] for j in jobs):
                        await self.deployment.create_job(live)
                    continue
                history=[s for s in sessions if s['role']==role and s['slot']==slot]
                previous=max(history,key=lambda s:s['incarnation']) if history else None
                restarts=previous.get('restart_count',0)+1 if previous else 0
                if previous:
                    delay=min(fleet['backoff_max_seconds'],fleet['backoff_initial_seconds']*2**min(restarts-1,60))
                    if self.clock.utc()<(previous.get('ended_at') or previous.get('heartbeat_at') or 0)+delay: continue
                session=await self.store.reserve(evaluation,role,slot,previous['incarnation']+1 if previous else 0,restarts)
                if session: await self.deployment.create_job(session)

    async def run(self,evaluation,monitor_seconds,stop):
        while not stop.is_set():
            try:
                await self.reconcile(evaluation)
            except Exception:
                try: await self.store.degraded(evaluation,'lifecycle_dependency_unavailable')
                except Exception:
                    __import__('logging').getLogger('foundry.lifecycle').error('lifecycle_persistence_unavailable')
            try: await asyncio.wait_for(stop.wait(),timeout=monitor_seconds)
            except asyncio.TimeoutError: pass
