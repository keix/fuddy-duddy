"""errno number -> name, for showing why a syscall failed (SPEC.md R11).

A syscall's raw result is a negative errno on failure; this turns that into a
name a reader recognizes (ENOENT, EACCES, ...).
"""

ERRNO_NAMES: dict[int, str] = {
    1: "EPERM",
    2: "ENOENT",
    3: "ESRCH",
    4: "EINTR",
    5: "EIO",
    6: "ENXIO",
    7: "E2BIG",
    8: "ENOEXEC",
    9: "EBADF",
    10: "ECHILD",
    11: "EAGAIN",
    12: "ENOMEM",
    13: "EACCES",
    14: "EFAULT",
    16: "EBUSY",
    17: "EEXIST",
    18: "EXDEV",
    19: "ENODEV",
    20: "ENOTDIR",
    21: "EISDIR",
    22: "EINVAL",
    23: "ENFILE",
    24: "EMFILE",
    25: "ENOTTY",
    27: "EFBIG",
    28: "ENOSPC",
    29: "ESPIPE",
    30: "EROFS",
    32: "EPIPE",
    34: "ERANGE",
    36: "ENAMETOOLONG",
    38: "ENOSYS",
    39: "ENOTEMPTY",
    40: "ELOOP",
    110: "ETIMEDOUT",
    111: "ECONNREFUSED",
    113: "EHOSTUNREACH",
}


def errno_name(result: int) -> str | None:
    """Name for a negative syscall result, or None if it did not fail."""
    if result >= 0:
        return None
    return ERRNO_NAMES.get(-result, f"errno {-result}")
