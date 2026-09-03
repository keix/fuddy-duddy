"""Wire events -> SyscallEvents (SPEC.md D1-D4).

Stateful: remembers the pending ENTER per pid so the matching EXIT can be
named. Pure Python; must not import pyxel.
"""

from .event import Event, ExitEvent, Phase, SpawnEvent, SyscallEvent
from .syscalls_x86_64 import NAMES
from .wire import WireEnter, WireEvent, WireExit, WireExited, WireSignaled, WireSpawn

# Syscalls whose first argument is a file descriptor. These get `fd` set from
# args[0] at ENTER time (SPEC.md D1).
_FD_FIRST: frozenset[str] = frozenset(
    {
        "read",
        "write",
        "close",
        "pread64",
        "pwrite64",
        "readv",
        "writev",
        "lseek",
        "fstat",
        "fsync",
        "fdatasync",
        "ftruncate",
        "fcntl",
        "flock",
        "fchdir",
        "fchmod",
        "fchown",
        "fstatfs",
        "dup",
        "dup2",
        "dup3",
        "sendfile",
        "getdents",
        "getdents64",
        "ioctl",
        "recvfrom",
        "sendto",
        "recvmsg",
        "sendmsg",
        "accept",
        "accept4",
        "connect",
        "bind",
        "listen",
        "shutdown",
        "epoll_wait",
        "epoll_ctl",
    }
)


def _name(nr: int) -> str:
    return NAMES.get(nr, f"sys_{nr}")


class Decoder:
    def __init__(self) -> None:
        # pid -> pending ENTER syscall name.
        self._pending: dict[int, str] = {}

    def push(self, event: WireEvent) -> list[Event]:
        if isinstance(event, WireEnter):
            name = _name(event.nr)
            self._pending[event.pid] = name
            path: str | None = None
            if name == "openat":
                path = event.strings.get(1)
            elif name == "execve":
                path = event.strings.get(0)
            fd = event.args[0] if name in _FD_FIRST else None
            return [
                SyscallEvent(
                    pid=event.pid,
                    name=name,
                    phase=Phase.ENTER,
                    path=path,
                    fd=fd,
                    args=event.args,
                )
            ]
        if isinstance(event, WireExit):
            name = self._pending.pop(event.pid, "?")
            return [
                SyscallEvent(
                    pid=event.pid,
                    name=name,
                    phase=Phase.EXIT,
                    result=event.ret,
                )
            ]
        if isinstance(event, WireSpawn):
            # D4: WireSpawn -> SpawnEvent(parent, child).
            return [SpawnEvent(parent=event.pid, child=event.child)]
        if isinstance(event, WireExited):
            # D3: process end -> ExitEvent. Drop any dangling pending ENTER; a
            # process that died mid-syscall has no matching EXIT coming.
            self._pending.pop(event.pid, None)
            return [ExitEvent(pid=event.pid, code=event.code)]
        if isinstance(event, WireSignaled):
            self._pending.pop(event.pid, None)
            return [ExitEvent(pid=event.pid, signal=event.sig)]
        return []
