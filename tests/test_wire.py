"""Contract for the wire protocol reference parser (SPEC.md)."""

import pytest

from fuddy_duddy.wire import (
    WireEnter,
    WireExit,
    WireExited,
    WireSignaled,
    WireSpawn,
    parse_line,
)


def test_parses_enter():
    event = parse_line("ENTER pid=1234 ts=99 nr=257 args=ffffff9c,7f00,0,0,0,0 str1=README.md")
    assert event == WireEnter(
        pid=1234,
        ts=99,
        nr=257,
        args=(0xFFFFFF9C, 0x7F00, 0, 0, 0, 0),
        strings={1: "README.md"},
    )


def test_parses_exit_with_error():
    event = parse_line("EXIT pid=1234 ts=100 ret=-2 err=1")
    assert event == WireExit(pid=1234, ts=100, ret=-2, err=True)


def test_parses_exited():
    assert parse_line("EXITED pid=1 ts=5 code=0") == WireExited(pid=1, ts=5, code=0)


def test_parses_signaled():
    assert parse_line("SIGNALED pid=1 ts=5 sig=9") == WireSignaled(pid=1, ts=5, sig=9)


def test_parses_spawn():
    assert parse_line("SPAWN pid=1200 ts=7 child=1201") == WireSpawn(pid=1200, ts=7, child=1201)


def test_fields_accepted_in_any_order():
    event = parse_line("EXIT err=0 ret=3 ts=1 pid=2")
    assert event == WireExit(pid=2, ts=1, ret=3, err=False)


def test_unescapes_strings():
    event = parse_line("ENTER pid=1 ts=1 nr=257 args=0,0,0,0,0,0 str1=a%20b%25c")
    assert isinstance(event, WireEnter)
    assert event.strings == {1: "a b%c"}


@pytest.mark.parametrize(
    "line",
    [
        "",
        "BOGUS pid=1",
        "ENTER pid=1 ts=1 nr=0 args=0,0,0",  # not six args
        "EXIT pid=1 ts=1",  # missing fields
        "ENTER pid=1 ts=1 nr=0 args=0,0,0,0,0,0 str1=%2",  # truncated escape
    ],
)
def test_malformed_lines_raise(line):
    with pytest.raises(ValueError):
        parse_line(line)
