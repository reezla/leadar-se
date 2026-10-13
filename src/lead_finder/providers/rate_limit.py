from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager


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
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = self.clock()
                while self.timestamps and now - self.timestamps[0] >= self.window_seconds:
                    self.timestamps.popleft()
                if len(self.timestamps) < self.requests:
                    self.timestamps.append(self.clock())
                    return
                delay = self.window_seconds - (now - self.timestamps[0])
            if delay > 0:
                self.sleep(delay)


class HostRequestGate:
    """Limits in-flight fetches globally and per site, with a gap between starts."""

    def __init__(
        self,
        *,
        max_in_flight: int,
        per_host_in_flight: int,
        host_gap_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_in_flight = max(1, max_in_flight)
        self.per_host_in_flight = max(1, per_host_in_flight)
        self.host_gap_seconds = host_gap_seconds
        self.clock = clock
        self.sleep = sleep
        self._global = threading.BoundedSemaphore(self.max_in_flight)
        self._guard = threading.Lock()
        self._hosts: dict[str, threading.BoundedSemaphore] = {}
        self._next_start: dict[str, float] = {}

    @contextmanager
    def slot(self, host: str) -> Iterator[None]:
        self.acquire(host)
        try:
            yield
        finally:
            self.release(host)

    def acquire(self, host: str) -> None:
        self._global.acquire()
        try:
            self._host(host).acquire()
        except BaseException:
            self._global.release()
            raise
        try:
            self._pause(host)
        except BaseException:
            self.release(host)
            raise

    def release(self, host: str) -> None:
        self._host(host).release()
        self._global.release()

    def _host(self, host: str) -> threading.BoundedSemaphore:
        with self._guard:
            gate = self._hosts.get(host)
            if gate is None:
                gate = threading.BoundedSemaphore(self.per_host_in_flight)
                self._hosts[host] = gate
            return gate

    def _pause(self, host: str) -> None:
        delay = 0.0
        if self.host_gap_seconds > 0:
            with self._guard:
                now = self.clock()
                earliest = self._next_start.get(host, now)
                delay = max(0.0, earliest - now)
                self._next_start[host] = max(earliest, now) + self.host_gap_seconds
        if delay > 0:
            self.sleep(delay)
