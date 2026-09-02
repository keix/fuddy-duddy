"""Semantic state of the observed system.

The contract is SPEC.md rules S1-S6, enforced by tests/test_model.py.
"""

from dataclasses import dataclass, field

from .event import SyscallEvent


@dataclass(frozen=True)
class FD:
    number: int
    target: str | None


@dataclass
class Process:
    pid: int
    name: str
    in_syscall: str | None = None
    last_result: int | None = None
    fds: dict[int, FD] = field(default_factory=dict)


class World:
    """Current state of the observed system.

    The scene draws this state; it never interprets events itself.
    """

    def __init__(self, process: Process) -> None:
        self.process = process

    def apply(self, event: SyscallEvent) -> SyscallEvent:
        """Apply one observed event to the world (SPEC.md S1-S6).

        Returns the event unchanged so callers can forward it to Scene.notify.
        """
        raise NotImplementedError
