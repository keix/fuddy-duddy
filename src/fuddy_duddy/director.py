"""Paces real-time events onto visual frames (SPEC.md P1-P4).

Observation is real-time; display is playback. The collector thread calls
feed(); the Pyxel loop calls poll(frame). Pure Python; must not import pyxel.
"""

import threading
from collections import deque

from .event import Event, Phase, SyscallEvent
from .source import EventSource

# Minimum frames between two released events, so bursts stay watchable.
MIN_GAP_FRAMES = 6
# After an ENTER, hold longer: its pulse must descend fully into kernel space
# before the matching EXIT is released and sends it back (P2).
ENTER_HOLD_FRAMES = 20


class Director(EventSource):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[Event] = deque()
        # Frame and phase of the last release; None until the first release.
        self._last_release: int | None = None
        self._last_phase: Phase | None = None

    def feed(self, event: Event) -> None:
        """Push an observed event (called from the collector thread)."""
        with self._lock:
            self._queue.append(event)

    def poll(self, frame: int) -> list[Event]:
        """Release due events for this frame (called from the Pyxel loop)."""
        with self._lock:
            if not self._queue:
                return []
            gap = ENTER_HOLD_FRAMES if self._last_phase is Phase.ENTER else MIN_GAP_FRAMES
            if self._last_release is not None and frame - self._last_release < gap:
                return []
            event = self._queue.popleft()
            self._last_release = frame
            self._last_phase = event.phase if isinstance(event, SyscallEvent) else None
            return [event]
