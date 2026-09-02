from dataclasses import dataclass

from .event import Phase, SyscallEvent


@dataclass
class Process:
    pid: int
    name: str
    in_syscall: str | None = None
    last_result: int | None = None


class World:
    """Current state of the observed system.

    The visualizer draws this state; it never interprets events itself.
    """

    def __init__(self, process: Process) -> None:
        self.process = process

    def apply(self, event: SyscallEvent) -> SyscallEvent:
        proc = self.process
        if event.phase is Phase.ENTER:
            proc.in_syscall = event.name
            proc.last_result = None
        else:
            proc.in_syscall = None
            proc.last_result = event.result
        return event
