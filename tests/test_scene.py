"""Semantic contract for the scene (SPEC.md R1-R9).

These tests are topological on purpose: they constrain which side of the
boundary things appear on and when, never exact coordinates or shapes.
"""

from fuddy_duddy.render import (
    BOUNDARY_Y,
    COL_FAIL,
    COL_OK,
    FD_BAR_Y,
    ZONE_LABELS,
    Line,
    Rect,
    zone_bounds,
)
from fuddy_duddy.subsystems import Subsystem
from helpers import circles, enter, exited, make_app, make_world, run_frames, spawn, texts

CLONE_THREAD = 0x00010000


def _pid_labels(commands: list[object]) -> int:
    return len([t for t in texts(commands) if t.text.startswith("pid ")])  # type: ignore[arg-type]


def test_all_processes_are_drawn_as_boxes():  # R12
    script = [(0, enter("fork")), (10, exited("fork", 1235)), (12, spawn(child=1235))]
    assert _pid_labels(run_frames(script, 40)) >= 2


def test_spawn_makes_the_child_box_appear():  # R13
    before = _pid_labels(run_frames([], 5))
    script = [(0, enter("fork")), (10, exited("fork", 1235)), (12, spawn(child=1235))]
    after = _pid_labels(run_frames(script, 40))
    assert after > before


def test_clone_thread_adds_a_marker_in_the_box():  # R14
    def userland_markers(script: list, frames: int) -> int:  # type: ignore[type-arg]
        return len([c for c in circles(run_frames(script, frames)) if c.y < BOUNDARY_Y])

    plain = userland_markers([], 40)
    threaded = userland_markers(
        [(0, enter("clone", args=(CLONE_THREAD, 0, 0, 0, 0, 0))), (30, spawn(child=1235))], 60
    )
    assert threaded > plain


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


def _top_line(script: list[tuple[int, object]], frames: int) -> list[str]:
    return [t.text for t in texts(run_frames(script, frames)) if t.y < 20]  # type: ignore[arg-type]


def test_failed_open_names_the_error_and_path():  # R11
    script = [(0, enter("openat", path="/lib/libfoo.so")), (40, exited("openat", -2))]
    top = _top_line(script, 60)
    assert any("ENOENT" in line and "/lib/libfoo.so" in line for line in top)


def test_success_shows_return_as_fd():  # R11
    script = [(0, enter("openat", path="README.md")), (40, exited("openat", 3))]
    assert any("fd 3" in line for line in _top_line(script, 60))


def test_read_success_shows_bytes():  # R11
    script = [(0, enter("read", fd=3)), (40, exited("read", 128))]
    assert any("128 bytes" in line for line in _top_line(script, 60))


def test_success_clears_a_prior_error():  # R11
    script = [
        (0, enter("openat", path="/miss")),
        (20, exited("openat", -2)),
        (30, enter("read", fd=3)),
        (60, exited("read", 64)),
    ]
    top = _top_line(script, 90)
    assert any("64 bytes" in line for line in top)
    assert not any("ENOENT" in line for line in top)


def test_status_line_fades():  # R11
    script = [(0, enter("openat", path="/lib/libfoo.so")), (40, exited("openat", -2))]
    assert not any("ENOENT" in t.text for t in texts(run_frames(script, 200)))


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


def test_subsystem_zones_are_labeled():  # R9
    labels = {t.text for t in texts(run_frames([], 1))}
    assert set(ZONE_LABELS.values()) <= labels


def _waiting_pulse_x(name: str, **kwargs: object) -> list[int]:
    # After ~18 frames of descent the pulse is waiting in the kernel (R4).
    commands = run_frames([(0, enter(name, **kwargs))], 30)  # type: ignore[arg-type]
    return [c.x for c in circles(commands) if c.y > BOUNDARY_Y]


def _in_zone(xs: list[int], sub: Subsystem) -> bool:
    x0, w = zone_bounds(sub)
    return any(x0 <= x < x0 + w for x in xs)


def test_file_syscall_lands_in_file_zone():  # R9
    assert _in_zone(_waiting_pulse_x("openat", path="README.md"), Subsystem.FILE)


def test_memory_syscall_lands_in_memory_zone():  # R9
    assert _in_zone(_waiting_pulse_x("mmap"), Subsystem.MEMORY)


def test_process_syscall_lands_in_process_zone():  # R9
    assert _in_zone(_waiting_pulse_x("clone"), Subsystem.PROCESS)


def _mem_zone_blocks(world: object) -> int:
    from fuddy_duddy.model import World
    from fuddy_duddy.scene import Scene

    assert isinstance(world, World)
    commands = Scene().render(world)
    x0, w = zone_bounds(Subsystem.MEMORY)
    return sum(
        1
        for c in commands
        if isinstance(c, Rect) and c.y > BOUNDARY_Y and x0 <= c.x < x0 + w
    )


def test_mmap_grows_and_munmap_shrinks_the_mem_zone():  # R10
    world = make_world()
    before = _mem_zone_blocks(world)
    world.apply(enter("mmap", args=(0, 4096, 3, 34, 0, 0)))
    world.apply(exited("mmap", 0x1000))
    mapped = _mem_zone_blocks(world)
    world.apply(enter("munmap", args=(0x1000, 4096, 0, 0, 0, 0)))
    world.apply(exited("munmap", 0))
    unmapped = _mem_zone_blocks(world)
    assert mapped > before
    assert unmapped < mapped
