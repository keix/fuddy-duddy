"""Semantic state of the observed system.

The contract is SPEC.md rules S0-S10, enforced by tests/test_model.py.
"""

from dataclasses import dataclass, field

from .event import Event, Phase, SpawnEvent, SyscallEvent

CLONE_THREAD = 0x00010000


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
    ppid: int = 0  # parent pid, 0 for the initial process (S9)
    in_syscall: str | None = None
    last_result: int | None = None
    fds: dict[int, FD] = field(default_factory=dict)
    regions: dict[int, MemoryRegion] = field(default_factory=dict)  # keyed by start
    threads: set[int] = field(default_factory=set)  # tids sharing this box (S9)


class World:
    """Current state of the observed system.

    The scene draws this state; it never interprets events itself.
    """

    def __init__(self, process: Process) -> None:
        self.processes: dict[int, Process] = {process.pid: process}
        self._initial_pid = process.pid
        # pid -> pending ENTER SyscallEvent, for pairing EXITs.
        self._pending: dict[int, SyscallEvent] = {}

    @property
    def process(self) -> Process:
        """The initial process (back-compat for a single-process world)."""
        return self.processes[self._initial_pid]

    def apply(self, event: Event) -> Event:
        """Apply one observed event to the world (SPEC.md S0-S10).

        Returns the event unchanged so callers can forward it to Scene.notify.
        """
        if isinstance(event, SpawnEvent):
            self._apply_spawn(event)
        else:
            self._apply_syscall(event)
        return event

    def _process_for(self, pid: int) -> Process:
        """Look up processes[pid], adopting the initial pid if it is 0 (S0)."""
        if self._initial_pid == 0 and 0 in self.processes:
            # S0: the initial process's real pid is unknown; adopt it and rekey.
            proc = self.processes.pop(0)
            proc.pid = pid
            self._initial_pid = pid
            self.processes[pid] = proc
            pending = self._pending.pop(0, None)
            if pending is not None:
                self._pending[pid] = pending
            return proc
        if pid not in self.processes:
            self.processes[pid] = Process(pid=pid, name="")
        return self.processes[pid]

    def _apply_syscall(self, event: SyscallEvent) -> None:
        proc = self._process_for(event.pid)
        if event.phase is Phase.ENTER:
            proc.in_syscall = event.name  # S1
            self._pending[proc.pid] = event
            return

        # Phase.EXIT
        pending = self._pending.get(proc.pid)
        proc.in_syscall = None  # S2
        if event.result is not None:
            proc.last_result = event.result  # S2

        # An EXIT pairs only when its name matches the pending ENTER's (S3).
        paired = pending if pending is not None and pending.name == event.name else None
        if paired is not None:
            self._pending.pop(proc.pid, None)

        result = event.result
        if result is None or paired is None:
            # result=None recorded verbatim; orphan/mismatched EXITs do S2 only.
            return
        if result < 0:
            return  # S4: failed syscall changes no further state.

        name = paired.name
        if name == "openat":
            proc.fds[result] = FD(number=result, target=paired.path)  # S3
        elif name == "close" and paired.fd is not None:
            proc.fds.pop(paired.fd, None)  # S5
        elif name == "mmap":
            length = paired.args[1] if len(paired.args) > 1 else 0
            proc.regions[result] = MemoryRegion(start=result, length=length)  # S7
        elif name == "munmap":
            start = paired.args[0] if paired.args else None
            if start is not None:
                proc.regions.pop(start, None)  # S8
        elif name == "execve" and paired.path is not None:
            proc.name = paired.path.rsplit("/", 1)[-1]  # S10

    def _apply_spawn(self, event: SpawnEvent) -> None:
        parent = self._process_for(event.parent)
        pending = self._pending.get(parent.pid)
        if (
            pending is not None
            and pending.name == "clone"
            and pending.args
            and pending.args[0] & CLONE_THREAD
        ):
            parent.threads.add(event.child)  # S9: shared box.
            return
        # S9: fork/vfork/plain clone -> a new process inheriting name and fds,
        # linked to its parent by ppid.
        self.processes[event.child] = Process(
            pid=event.child,
            name=parent.name,
            ppid=parent.pid,
            fds=dict(parent.fds),
        )
