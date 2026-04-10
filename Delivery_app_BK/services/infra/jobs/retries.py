from __future__ import annotations

from dataclasses import dataclass

from rq import Retry


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    intervals: tuple[int, ...]

    def to_rq_retry(self) -> Retry:
        return Retry(max=self.max_attempts, interval=list(self.intervals))


REALTIME_RETRY_POLICY = RetryPolicy(max_attempts=2, intervals=(5,))
MESSAGING_RETRY_POLICY = RetryPolicy(max_attempts=5, intervals=(30, 120, 300, 900))
DEFAULT_RETRY_POLICY = RetryPolicy(max_attempts=3, intervals=(10, 60))
