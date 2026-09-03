"""Classify a syscall by the kernel subsystem it touches (SPEC.md R9).

Static table, by design: the classification is the contract, not something to
be inferred. An unclassified syscall is OTHER, which still crosses the boundary
(R8) but does not target a labeled zone.
"""

from enum import Enum, auto


class Subsystem(Enum):
    FILE = auto()
    MEMORY = auto()
    PROCESS = auto()
    NET = auto()
    OTHER = auto()


_CLASSIFY: dict[str, Subsystem] = {
    # Files and descriptors.
    "open": Subsystem.FILE,
    "openat": Subsystem.FILE,
    "openat2": Subsystem.FILE,
    "creat": Subsystem.FILE,
    "close": Subsystem.FILE,
    "read": Subsystem.FILE,
    "write": Subsystem.FILE,
    "pread64": Subsystem.FILE,
    "pwrite64": Subsystem.FILE,
    "readv": Subsystem.FILE,
    "writev": Subsystem.FILE,
    "lseek": Subsystem.FILE,
    "stat": Subsystem.FILE,
    "fstat": Subsystem.FILE,
    "lstat": Subsystem.FILE,
    "newfstatat": Subsystem.FILE,
    "statx": Subsystem.FILE,
    "access": Subsystem.FILE,
    "faccessat": Subsystem.FILE,
    "getdents64": Subsystem.FILE,
    "statfs": Subsystem.FILE,
    "fstatfs": Subsystem.FILE,
    "fadvise64": Subsystem.FILE,
    "fcntl": Subsystem.FILE,
    "dup": Subsystem.FILE,
    "dup2": Subsystem.FILE,
    "dup3": Subsystem.FILE,
    "pipe": Subsystem.FILE,
    "pipe2": Subsystem.FILE,
    # Memory.
    "mmap": Subsystem.MEMORY,
    "munmap": Subsystem.MEMORY,
    "mremap": Subsystem.MEMORY,
    "mprotect": Subsystem.MEMORY,
    "madvise": Subsystem.MEMORY,
    "brk": Subsystem.MEMORY,
    "mlock": Subsystem.MEMORY,
    "munlock": Subsystem.MEMORY,
    # Processes and threads.
    "clone": Subsystem.PROCESS,
    "clone3": Subsystem.PROCESS,
    "fork": Subsystem.PROCESS,
    "vfork": Subsystem.PROCESS,
    "execve": Subsystem.PROCESS,
    "execveat": Subsystem.PROCESS,
    "exit": Subsystem.PROCESS,
    "exit_group": Subsystem.PROCESS,
    "wait4": Subsystem.PROCESS,
    "waitid": Subsystem.PROCESS,
    "kill": Subsystem.PROCESS,
    "arch_prctl": Subsystem.PROCESS,
    "set_tid_address": Subsystem.PROCESS,
    # Network.
    "socket": Subsystem.NET,
    "socketpair": Subsystem.NET,
    "connect": Subsystem.NET,
    "accept": Subsystem.NET,
    "accept4": Subsystem.NET,
    "bind": Subsystem.NET,
    "listen": Subsystem.NET,
    "sendto": Subsystem.NET,
    "recvfrom": Subsystem.NET,
    "sendmsg": Subsystem.NET,
    "recvmsg": Subsystem.NET,
    "shutdown": Subsystem.NET,
    "getsockname": Subsystem.NET,
    "getpeername": Subsystem.NET,
    "setsockopt": Subsystem.NET,
    "getsockopt": Subsystem.NET,
}


def classify(name: str) -> Subsystem:
    return _CLASSIFY.get(name, Subsystem.OTHER)
