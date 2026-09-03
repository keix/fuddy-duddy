"""End-to-end contract for the C tracer (SPEC.md "Collector wire protocol").

The tracer runs a deterministic fixture child and must emit the child's
syscall story on stderr. Assertions are subsequence-based: libc startup
noise before and between the interesting syscalls is expected and ignored.
"""

import os
import select
import subprocess
import time
from pathlib import Path

import pytest

from fuddy_duddy.syscalls_x86_64 import NR
from fuddy_duddy.wire import WireEnter, WireEvent, WireExit, WireExited, parse_line

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR = ROOT / "collector"
STORY_TEXT = b"hello fuddy\n"


@pytest.fixture(scope="session")
def tracer() -> Path:
    subprocess.run(["make", "-C", str(COLLECTOR)], check=True, capture_output=True)
    return COLLECTOR / "tracer"


def parse_stream(data: bytes) -> list[WireEvent]:
    return [parse_line(line) for line in data.decode(errors="replace").splitlines() if line]


def enter_index(events: list[WireEvent], nr: int, start: int = 0, **preds: object) -> int:
    """Index of the first ENTER of syscall `nr` at/after `start` matching preds."""
    for i in range(start, len(events)):
        event = events[i]
        if not isinstance(event, WireEnter) or event.nr != nr:
            continue
        if "arg0" in preds and event.args[0] != preds["arg0"]:
            continue
        if "str1" in preds and event.strings.get(1) != preds["str1"]:
            continue
        return i
    raise AssertionError(f"no ENTER nr={nr} ({preds}) after index {start}")


def exit_of(events: list[WireEvent], i: int) -> WireExit:
    """Per contract, a single-threaded child's EXIT immediately follows its ENTER."""
    event = events[i + 1]
    assert isinstance(event, WireExit), f"event after ENTER is {event!r}"
    return event


def run_story(tracer: Path, tmp_path: Path) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    story_file = tmp_path / "story.txt"
    story_file.write_bytes(STORY_TEXT)
    proc = subprocess.run(
        [str(tracer), str(COLLECTOR / "fixtures" / "story"), str(story_file)],
        capture_output=True,
        timeout=10,
        check=False,  # the exit code is itself under test
    )
    return proc, story_file


def test_story_syscall_sequence(tracer: Path, tmp_path: Path) -> None:
    proc, story_file = run_story(tracer, tmp_path)
    events = parse_stream(proc.stderr)

    i = enter_index(events, NR["openat"], str1=str(story_file))
    fd = exit_of(events, i).ret
    assert fd >= 0

    i = enter_index(events, NR["read"], start=i, arg0=fd)
    assert exit_of(events, i).ret == len(STORY_TEXT)

    i = enter_index(events, NR["write"], start=i, arg0=1)
    assert exit_of(events, i).ret == len(STORY_TEXT)

    i = enter_index(events, NR["close"], start=i, arg0=fd)
    assert exit_of(events, i).ret == 0

    i = enter_index(events, NR["openat"], start=i, str1="/fuddy-duddy-missing")
    failed = exit_of(events, i)
    assert failed.err
    assert failed.ret == -2  # ENOENT

    last = events[-1]
    assert isinstance(last, WireExited)
    assert last.code == 0


def test_timestamps_are_monotonic(tracer: Path, tmp_path: Path) -> None:
    proc, _ = run_story(tracer, tmp_path)
    stamps = [e.ts for e in parse_stream(proc.stderr)]
    assert stamps == sorted(stamps)
    assert stamps, "no events at all"


def test_child_stdio_passes_through(tracer: Path, tmp_path: Path) -> None:
    proc, _ = run_story(tracer, tmp_path)
    assert proc.stdout == STORY_TEXT


def test_tracer_mirrors_child_exit_code(tracer: Path, tmp_path: Path) -> None:
    proc, _ = run_story(tracer, tmp_path)
    assert proc.returncode == 0


def test_enter_is_emitted_while_child_is_blocked(tracer: Path) -> None:
    """The flush contract: ENTER of a blocking read must arrive before EXIT."""
    proc = subprocess.Popen(
        [str(tracer), str(COLLECTOR / "fixtures" / "block")],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stderr is not None
    os.set_blocking(proc.stderr.fileno(), False)
    try:
        buffer = b""
        deadline = time.monotonic() + 5.0
        blocked_enter_seen = False
        while time.monotonic() < deadline and not blocked_enter_seen:
            ready, _, _ = select.select([proc.stderr], [], [], 0.1)
            if not ready:
                continue
            chunk = proc.stderr.read()
            if chunk is None:
                continue
            if chunk == b"":
                break  # EOF: tracer died without ever blocking
            buffer += chunk
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                if not line:
                    continue
                event = parse_line(line.decode(errors="replace"))
                if isinstance(event, WireEnter) and event.nr == NR["read"] and event.args[0] == 0:
                    blocked_enter_seen = True
        assert blocked_enter_seen, "no ENTER for the blocking read(0) arrived while blocked"

        proc.stdin.write(b"x")
        proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        proc.kill()
        proc.wait()
