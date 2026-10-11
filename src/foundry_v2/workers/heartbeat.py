"""A dedicated process owns its HTTP lane independently of model/CPU work."""
import multiprocessing
import time

import httpx

from foundry_v2.contracts.models import new_id


def heartbeat_process(stop,url,token,session,incarnation,interval,ca_file,allow_http):
    if not url.startswith('https://') and not (allow_http and url.startswith('http://')):
        raise ValueError('Explicit private HTTP override required')
    with httpx.Client(timeout=min(interval,10),verify=ca_file,trust_env=False) as client:
        while not stop.is_set():
            try:
                response=client.post(url,headers={'Authorization':'Bearer '+token,'Idempotency-Key':new_id()},
                                     json={'session_id':session,'incarnation':incarnation,'last_event_sequence':0})
                if response.status_code in (401,403,409): return
            except httpx.HTTPError:
                pass  # Partition cannot fabricate receipt liveness; owner reaps stale holders.
            stop.wait(interval)


class HeartbeatSender:
    def __init__(self,url,token,session,incarnation,interval,ca_file=True,allow_http=False):
        if interval<=0: raise ValueError('Positive heartbeat interval required')
        self.context=multiprocessing.get_context('spawn')
        self.stop=self.context.Event()
        self.process=self.context.Process(target=heartbeat_process,args=(self.stop,url,token,session,incarnation,interval,ca_file,allow_http),daemon=True)

    def start(self):
        self.process.start()

    def close(self):
        self.stop.set()
        if self.process.pid:
            self.process.join(timeout=12)
            if self.process.is_alive(): self.process.terminate(); self.process.join(timeout=5)
