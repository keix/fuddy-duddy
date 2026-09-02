"""Semantic state of the observed system.

The contract is SPEC.md rules S1-S6, enforced by tests/test_model.py.
"""

from dataclasses import dataclass, field

from .event import Phase, SyscallEvent


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
        self._pending: SyscallEvent | None = None

    def apply(self, event: SyscallEvent) -> SyscallEvent:
        """Apply one observed event to the world (SPEC.md S1-S6).

        Returns the event unchanged so callers can forward it to Scene.notify.
        """
        process = self.process
        if event.phase is Phase.ENTER:
            # S1: the process is now inside this syscall.
            process.in_syscall = event.name
            self._pending = event
            return event

        # S2: EXIT clears the in-flight marker and records the result.
        pending = self._pending
        self._pending = None
        process.in_syscall = None
        process.last_result = event.result

        # S4/S6: failures and unknown syscalls change nothing beyond S2.
        if event.result is None or event.result < 0:
            return event

        if event.name == "openat" and pending is not None and pending.name == "openat":
            # S3: pair the EXIT's fd number with the ENTER's path.
            process.fds[event.result] = FD(number=event.result, target=pending.path)
        elif (
            event.name == "close"
            and pending is not None
            and pending.name == "close"
            and pending.fd is not None
        ):
            # S5: the fd being closed was named at ENTER time.
            process.fds.pop(pending.fd, None)
        return event
