from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class SlidingWindowRateLimiter:
    def __init__(
        self,
        requests: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self.clock = clock
        self.sleep = sleep
        self.timestamps: deque[float] = deque()

    def wait(self) -> None:
        now = self.clock()
        while self.timestamps and now - self.timestamps[0] >= self.window_seconds:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.requests:
            delay = self.window_seconds - (now - self.timestamps[0])
            if delay > 0:
                self.sleep(delay)
            now = self.clock()
            while self.timestamps and now - self.timestamps[0] >= self.window_seconds:
                self.timestamps.popleft()
        self.timestamps.append(self.clock())
