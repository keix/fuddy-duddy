"""Contract for the wire->SyscallEvent decoder (SPEC.md D1-D3)."""

from fuddy_duddy.decode import Decoder
from fuddy_duddy.event import Phase
from fuddy_duddy.syscalls_x86_64 import NR
from fuddy_duddy.wire import WireEnter, WireExit, WireExited, WireSignaled

ARGS0 = (0, 0, 0, 0, 0, 0)


def enter(nr: int, args: tuple[int, ...] = ARGS0, strings: dict[int, str] | None = None) -> WireEnter:
    return WireEnter(pid=7, ts=0, nr=nr, args=(args + ARGS0)[:6], strings=strings or {})  # type: ignore[arg-type]


def test_enter_openat_carries_path():  # D1
    [event] = Decoder().push(enter(NR["openat"], strings={1: "README.md"}))
    assert event.phase is Phase.ENTER
    assert event.name == "openat"
    assert event.path == "README.md"
    assert event.pid == 7


def test_enter_close_carries_fd():  # D1
    [event] = Decoder().push(enter(NR["close"], args=(5,)))
    assert event.name == "close"
    assert event.fd == 5


def test_unknown_number_becomes_sys_nr():  # D1
    [event] = Decoder().push(enter(9999))
    assert event.name == "sys_9999"
    assert event.phase is Phase.ENTER


def test_enter_carries_raw_args():  # D1
    [event] = Decoder().push(enter(NR["mmap"], args=(0, 4096, 3, 34, 0, 0)))
    assert event.args == (0, 4096, 3, 34, 0, 0)


def test_exit_takes_name_from_pending_enter():  # D2
    decoder = Decoder()
    decoder.push(enter(NR["openat"], strings={1: "README.md"}))
    [event] = decoder.push(WireExit(pid=7, ts=1, ret=3, err=False))
    assert event.phase is Phase.EXIT
    assert event.name == "openat"
    assert event.result == 3


def test_exit_reports_negative_result_on_failure():  # D2
    decoder = Decoder()
    decoder.push(enter(NR["openat"], strings={1: "missing"}))
    [event] = decoder.push(WireExit(pid=7, ts=1, ret=-2, err=True))
    assert event.result == -2


def test_process_end_yields_nothing():  # D3
    decoder = Decoder()
    assert decoder.push(WireExited(pid=7, ts=1, code=0)) == []
    assert decoder.push(WireSignaled(pid=7, ts=1, sig=9)) == []
