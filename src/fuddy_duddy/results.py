"""Render a syscall's return value with the meaning its number carries.

The return register (rax) means different things per syscall: a file
descriptor, a byte count, a mapped address, or a plain number. On failure it
is a negative errno. This turns a raw result into a readable token (SPEC.md
R11).
"""

from .errno_names import errno_name

# Syscalls whose successful result is a new file descriptor.
_FD_RESULT = frozenset(
    {
        "open",
        "openat",
        "openat2",
        "creat",
        "socket",
        "accept",
        "accept4",
        "dup",
        "dup2",
        "dup3",
        "epoll_create1",
        "eventfd2",
        "memfd_create",
        "timerfd_create",
        "signalfd4",
        "inotify_init1",
    }
)

# Syscalls whose successful result is a byte count.
_BYTES_RESULT = frozenset(
    {
        "read",
        "write",
        "pread64",
        "pwrite64",
        "readv",
        "writev",
        "preadv",
        "pwritev",
        "sendto",
        "recvfrom",
        "sendmsg",
        "recvmsg",
        "sendfile",
        "copy_file_range",
        "getdents64",
        "getrandom",
    }
)

# Syscalls whose successful result is an address.
_ADDR_RESULT = frozenset({"mmap", "mremap", "brk", "shmat"})


def format_result(name: str, result: int) -> str:
    """A short token for `result` in the context of syscall `name`."""
    if result < 0:
        return errno_name(result) or "error"
    if name in _ADDR_RESULT:
        return f"0x{result:x}"
    if name in _BYTES_RESULT:
        return f"{result} bytes"
    if name in _FD_RESULT:
        return f"fd {result}"
    return str(result)
