"""Conservative sequential quote request pacing; no automatic retries.

Does not establish broker rate limits. Caller must separately verify
KIS account/application limits before increasing the symbol universe.
"""
import time

class RequestPacer:
    def __init__(self, min_interval_seconds=0.5, *, clock=None, sleep=None):
        if not 0.1 <= min_interval_seconds <= 10:
            raise ValueError("invalid interval")
        self.interval=float(min_interval_seconds)
        self.clock=clock or time.monotonic
        self.sleep=sleep or time.sleep
        self.last_started=None

    def before_request(self):
        now=self.clock()
        if self.last_started is not None:
            wait=max(0.0,self.interval-(now-self.last_started))
            if wait:
                self.sleep(wait)
                now=self.clock()
        self.last_started=now
