"""Semantic state of the observed system.

The contract is SPEC.md rules S1-S6, enforced by tests/test_model.py.
"""

from dataclasses import dataclass, field

from .event import Phase, SyscallEvent


@dataclass(frozen=True)
class FD:
    number: int
    target: str | None


@dataclass(frozen=True)
class MemoryRegion:
    start: int
    length: int


@dataclass
class Process:
    pid: int
    name: str
    in_syscall: str | None = None
    last_result: int | None = None
    fds: dict[int, FD] = field(default_factory=dict)
    regions: dict[int, MemoryRegion] = field(default_factory=dict)  # keyed by start


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
        if process.pid == 0:
            # S0: adopt the real pid from the first observed event.
            process.pid = event.pid
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
        elif event.name == "mmap" and pending is not None and pending.name == "mmap":
            # S7: the mapped address (result) is the region start; its length
            # was the ENTER's args[1].
            length = pending.args[1] if len(pending.args) > 1 else 0
            process.regions[event.result] = MemoryRegion(start=event.result, length=length)
        elif (
            event.name == "munmap"
            and pending is not None
            and pending.name == "munmap"
            and pending.args
        ):
            # S8: unmap the region at the ENTER's args[0].
            process.regions.pop(pending.args[0], None)
        return event
