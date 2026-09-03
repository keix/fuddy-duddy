from typing import Protocol

from .event import Event


class EventSource(Protocol):
    """Produces observed events, keyed by visual frame number."""

    def poll(self, frame: int) -> list[Event]: ...


class ScriptedSource:
    """Fake event source: a fixed script of (frame, event) pairs.

    The strace collector replaces this later behind the same protocol.
    """

    def __init__(
        self,
        script: list[tuple[int, Event]],
        loop: bool = False,
        loop_pause: int = 45,
    ) -> None:
        self.script: list[tuple[int, Event]] = sorted(script, key=lambda item: item[0])
        self.loop = loop
        last = self.script[-1][0] if self.script else 0
        self.period = last + loop_pause

    def poll(self, frame: int) -> list[Event]:
        if self.loop:
            frame = frame % self.period
        return [event for when, event in self.script if when == frame]
