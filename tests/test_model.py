"""Semantic contract for the world model (SPEC.md S0-S6)."""

from fuddy_duddy.model import Process, World
from helpers import PID, enter, exited, make_world


def test_pid_is_adopted_from_first_event_when_unknown():  # S0
    world = World(Process(pid=0, name="cat"))
    world.apply(enter("read", fd=3))
    assert world.process.pid == PID


def test_enter_marks_process_in_syscall():  # S1
    world = make_world()
    world.apply(enter("read", fd=3))
    assert world.process.in_syscall == "read"


def test_exit_clears_syscall_and_records_result():  # S2
    world = make_world()
    world.apply(enter("read", fd=3))
    world.apply(exited("read", 128))
    assert world.process.in_syscall is None
    assert world.process.last_result == 128


def test_openat_creates_fd():  # S3
    world = make_world()
    world.apply(enter("openat", path="README.md"))
    world.apply(exited("openat", 3))
    assert 3 in world.process.fds
    assert world.process.fds[3].target == "README.md"


def test_failed_open_does_not_create_fd():  # S4
    world = make_world()
    world.apply(enter("openat", path="missing.txt"))
    world.apply(exited("openat", -2))
    assert world.process.fds == {}
    assert world.process.last_result == -2


def test_close_removes_fd():  # S5
    world = make_world()
    world.apply(enter("openat", path="README.md"))
    world.apply(exited("openat", 3))
    world.apply(enter("close", fd=3))
    world.apply(exited("close", 0))
    assert 3 not in world.process.fds


def test_unknown_syscall_changes_no_state():  # S6
    world = make_world()
    world.apply(enter("ioctl", fd=0))
    world.apply(exited("ioctl", 0))
    assert world.process.fds == {}
    assert world.process.in_syscall is None
    assert world.process.last_result == 0
