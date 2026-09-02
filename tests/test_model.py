from fuddy_duddy.event import Phase, SyscallEvent
from fuddy_duddy.model import Process, World


def make_world() -> World:
    return World(Process(pid=1234, name="cat"))


def test_enter_marks_process_in_syscall():
    world = make_world()
    world.apply(SyscallEvent(1234, "read", Phase.ENTER))
    assert world.process.in_syscall == "read"
    assert world.process.last_result is None


def test_exit_clears_syscall_and_records_result():
    world = make_world()
    world.apply(SyscallEvent(1234, "read", Phase.ENTER))
    world.apply(SyscallEvent(1234, "read", Phase.EXIT, 128))
    assert world.process.in_syscall is None
    assert world.process.last_result == 128
