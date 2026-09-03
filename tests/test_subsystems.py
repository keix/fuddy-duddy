"""Contract for syscall -> subsystem classification (SPEC.md R9)."""

import pytest

from fuddy_duddy.subsystems import Subsystem, classify


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("openat", Subsystem.FILE),
        ("read", Subsystem.FILE),
        ("write", Subsystem.FILE),
        ("close", Subsystem.FILE),
        ("mmap", Subsystem.MEMORY),
        ("brk", Subsystem.MEMORY),
        ("munmap", Subsystem.MEMORY),
        ("clone", Subsystem.PROCESS),
        ("execve", Subsystem.PROCESS),
        ("exit_group", Subsystem.PROCESS),
        ("socket", Subsystem.NET),
        ("connect", Subsystem.NET),
    ],
)
def test_known_syscalls_classify(name: str, expected: Subsystem) -> None:
    assert classify(name) == expected


def test_unknown_syscall_is_other() -> None:
    assert classify("sys_9999") == Subsystem.OTHER
    assert classify("frobnicate") == Subsystem.OTHER
