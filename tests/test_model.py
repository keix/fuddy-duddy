"""Semantic contract for the world model (SPEC.md S0-S11)."""

from fuddy_duddy.model import Process, World
from helpers import PID, died, enter, exited, make_world, spawn

CLONE_THREAD = 0x00010000


def test_fork_creates_a_child_process():  # S9
    world = make_world()  # pid 1234, name "cat"
    world.apply(enter("fork"))
    world.apply(exited("fork", PID + 1))
    world.apply(spawn(child=PID + 1))
    assert PID + 1 in world.processes
    assert world.processes[PID + 1].name == "cat"  # inherited
    assert world.processes[PID + 1].ppid == PID  # linked to parent
    assert PID + 1 not in world.process.threads


def test_clone_thread_adds_a_thread_not_a_process():  # S9
    world = make_world()
    world.apply(enter("clone", args=(CLONE_THREAD, 0, 0, 0, 0, 0)))
    world.apply(spawn(child=PID + 1))
    assert PID + 1 in world.process.threads
    assert PID + 1 not in world.processes


def test_exit_removes_a_child_process():  # S11
    world = make_world()  # pid 1234
    world.apply(enter("fork"))
    world.apply(exited("fork", PID + 1))
    world.apply(spawn(child=PID + 1))
    assert PID + 1 in world.processes
    world.apply(died(PID + 1))
    assert PID + 1 not in world.processes


def test_exit_keeps_the_initial_process():  # S11
    world = make_world()  # pid 1234 is the root
    world.apply(died(PID))
    assert PID in world.processes  # the frame of reference stays
    assert world.process.pid == PID


def test_exit_of_unknown_pid_is_ignored():  # S11
    world = make_world()
    world.apply(died(PID + 99))  # never spawned
    assert set(world.processes) == {PID}


def test_execve_switches_the_process_name():  # S10
    world = make_world()  # name "cat"
    world.apply(enter("execve", path="/bin/ls"))
    world.apply(exited("execve", 0))
    assert world.process.name == "ls"


def test_a_syscall_applies_to_its_own_process():  # multi-process
    world = make_world()  # 1234
    world.apply(enter("fork"))
    world.apply(exited("fork", PID + 1))
    world.apply(spawn(child=PID + 1))
    # The child opens a file; the parent must be unaffected.
    world.apply(enter("openat", pid=PID + 1, path="child.txt"))
    world.apply(exited("openat", 5, pid=PID + 1))
    assert 5 in world.processes[PID + 1].fds
    assert 5 not in world.process.fds


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


def test_mmap_creates_region():  # S7
    world = make_world()
    world.apply(enter("mmap", args=(0, 4096, 3, 34, 0, 0)))
    world.apply(exited("mmap", 0x1000))
    assert 0x1000 in world.process.regions
    assert world.process.regions[0x1000].length == 4096


def test_failed_mmap_creates_no_region():  # S7
    world = make_world()
    world.apply(enter("mmap", args=(0, 4096, 3, 34, 0, 0)))
    world.apply(exited("mmap", -12))  # ENOMEM
    assert world.process.regions == {}


def test_munmap_removes_region():  # S8
    world = make_world()
    world.apply(enter("mmap", args=(0, 4096, 3, 34, 0, 0)))
    world.apply(exited("mmap", 0x1000))
    world.apply(enter("munmap", args=(0x1000, 4096, 0, 0, 0, 0)))
    world.apply(exited("munmap", 0))
    assert 0x1000 not in world.process.regions


def test_unknown_syscall_changes_no_state():  # S6
    world = make_world()
    world.apply(enter("ioctl", fd=0))
    world.apply(exited("ioctl", 0))
    assert world.process.fds == {}
    assert world.process.in_syscall is None
    assert world.process.last_result == 0
