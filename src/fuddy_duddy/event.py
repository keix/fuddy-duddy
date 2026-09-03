from dataclasses import dataclass
from enum import Enum, auto


class Phase(Enum):
    ENTER = auto()
    EXIT = auto()


@dataclass(frozen=True)
class SyscallEvent:
    pid: int
    name: str
    phase: Phase
    result: int | None = None
    path: str | None = None
    fd: int | None = None
    args: tuple[int, ...] = ()  # raw syscall arguments, on ENTER (e.g. mmap size)


@dataclass(frozen=True)
class SpawnEvent:
    """A process created a child via fork/clone/vfork (SPEC.md S9)."""

    parent: int
    child: int


@dataclass(frozen=True)
class ExitEvent:
    """A traced process terminated (SPEC.md S11).

    `code` is set for a normal exit, `signal` for a kill; exactly one is set.
    """

    pid: int
    code: int | None = None
    signal: int | None = None


# Anything that flows from the collector through the director into the world.
Event = SyscallEvent | SpawnEvent | ExitEvent
