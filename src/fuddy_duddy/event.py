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


# Anything that flows from the collector through the director into the world.
Event = SyscallEvent | SpawnEvent
