"""Semantic contract for the scene (SPEC.md R1-R8).

These tests are topological on purpose: they constrain which side of the
boundary things appear on and when, never exact coordinates or shapes.
"""

from fuddy_duddy.render import BOUNDARY_Y, COL_FAIL, COL_OK, FD_BAR_Y, Line, Rect
from helpers import circles, enter, exited, make_app, run_frames, texts


def near_boundary(command: object) -> bool:
    if isinstance(command, Rect):
        return abs(command.y - BOUNDARY_Y) <= 2
    if isinstance(command, Line):
        return abs(command.y1 - BOUNDARY_Y) <= 2 and abs(command.y2 - BOUNDARY_Y) <= 2
    return False


def test_boundary_always_drawn():  # R1
    commands = run_frames([], 1)
    assert any(near_boundary(c) for c in commands)


def test_space_labels_drawn():  # R2
    commands = run_frames([], 1)
    labels = {t.text: t for t in texts(commands)}
    assert labels["USERLAND"].y < BOUNDARY_Y
    assert labels["KERNEL SPACE"].y > BOUNDARY_Y


def test_read_enter_crosses_boundary():  # R3
    commands = run_frames([(0, enter("read", fd=3))], 30)
    assert any(c.y > BOUNDARY_Y for c in circles(commands))


def test_blocking_read_stays_in_kernel():  # R4
    commands = run_frames([(0, enter("read", fd=3))], 120)
    assert any(c.y > BOUNDARY_Y for c in circles(commands))
    assert any(t.text == "read" and t.y > BOUNDARY_Y for t in texts(commands))


def test_read_exit_returns_to_userland():  # R5
    script = [(0, enter("read", fd=3)), (40, exited("read", 128))]
    commands = run_frames(script, 120)
    assert not any(c.y > BOUNDARY_Y for c in circles(commands))
    assert not any(t.text == "read" and t.y > BOUNDARY_Y for t in texts(commands))
    assert any(
        t.text == "= 128" and t.y < BOUNDARY_Y and t.color == COL_OK for t in texts(commands)
    )


def test_result_waits_for_the_pulse_to_return():  # R5 temporal invariant
    script = [(0, enter("read", fd=3)), (40, exited("read", 128))]
    app = make_app(script)
    for _ in range(120):
        app.step()
        commands = app.commands()
        pulse_in_kernel = any(c.y > BOUNDARY_Y for c in circles(commands))
        result_shown = any(t.text == "= 128" for t in texts(commands))
        assert not (pulse_in_kernel and result_shown)


def test_failed_result_shows_then_fades():  # R6
    script = [(0, enter("openat", path="missing.txt")), (40, exited("openat", -2))]
    # Shortly after the pulse returns, the failure is visible and red.
    early = texts(run_frames(script, 60))
    assert any(t.text == "= -2" and t.y < BOUNDARY_Y and t.color == COL_FAIL for t in early)
    # Long after, it has faded — unlike a success, which persists (R5).
    late = texts(run_frames(script, 120))
    assert not any(t.text == "= -2" for t in late)


def test_open_fd_appears_in_fd_bar():  # R7
    script = [(0, enter("openat", path="README.md")), (40, exited("openat", 3))]
    commands = run_frames(script, 120)
    assert any(t.text.startswith("3") and t.y >= FD_BAR_Y for t in texts(commands))


def test_closed_fd_leaves_fd_bar():  # R7
    script = [
        (0, enter("openat", path="README.md")),
        (40, exited("openat", 3)),
        (80, enter("close", fd=3)),
        (120, exited("close", 0)),
    ]
    commands = run_frames(script, 200)
    assert not any(t.y >= FD_BAR_Y for t in texts(commands))


def test_unknown_syscall_still_crosses_boundary():  # R8
    commands = run_frames([(0, enter("ioctl", fd=0))], 30)
    assert any(c.y > BOUNDARY_Y for c in circles(commands))
