"""Wire events -> SyscallEvents (SPEC.md D1-D3).

Stateful: remembers the pending ENTER per pid so the matching EXIT can be
named. Pure Python; must not import pyxel.
"""

from .event import Phase, SyscallEvent
from .syscalls_x86_64 import NAMES
from .wire import WireEnter, WireEvent, WireExit

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

    def push(self, event: WireEvent) -> list[SyscallEvent]:
        if isinstance(event, WireEnter):
            name = _name(event.nr)
            self._pending[event.pid] = name
            path = event.strings.get(1) if name == "openat" else None
            fd = event.args[0] if name in _FD_FIRST else None
            return [
                SyscallEvent(
                    pid=event.pid,
                    name=name,
                    phase=Phase.ENTER,
                    path=path,
                    fd=fd,
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
        # WireExited / WireSignaled (D3): no SyscallEvent.
        return []
