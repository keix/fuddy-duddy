"""Paces real-time events onto visual frames (SPEC.md P1-P4).

Observation is real-time; display is playback. The collector thread calls
feed(); the Pyxel loop calls poll(frame). Pure Python; must not import pyxel.
"""

import threading
from collections import deque

from .event import SyscallEvent
from .source import EventSource

# Minimum frames between two released events, so bursts stay watchable.
MIN_GAP_FRAMES = 6


class Director(EventSource):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[SyscallEvent] = deque()
        # Frame of the last release; None until the first release happens.
        self._last_release: int | None = None

    def feed(self, event: SyscallEvent) -> None:
        """Push an observed event (called from the collector thread)."""
        with self._lock:
            self._queue.append(event)

    def poll(self, frame: int) -> list[SyscallEvent]:
        """Release due events for this frame (called from the Pyxel loop)."""
        with self._lock:
            if not self._queue:
                return []
            if self._last_release is not None and frame - self._last_release < MIN_GAP_FRAMES:
                return []
            self._last_release = frame
            return [self._queue.popleft()]
