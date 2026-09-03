"""Visual state machine: turns world state and events into render commands.

The contract is SPEC.md rules R1-R8, enforced by tests/test_scene.py.
This module must not import pyxel; it emits render.Command values only.

The picture it paints (R1-R8):

    +----------------------------------+
    |  USERLAND      [cat pid 1234]    |   process box, in-flight syscall,
    |                     |            |   result popup ("= 128")
    |=========== boundary =============|   R1/R2
    |  KERNEL SPACE       o  read      |   pulse waits here while blocked
    |                                  |
    |  FDS  [3 README.md]              |   R7 fd bar
    +----------------------------------+

A syscall is a pulse: it leaves the process box, descends, punches through
the boundary, waits in kernel space while blocked, and rides back up colored
by success or failure. All transient effects die well within 30 frames.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from .event import Phase, SyscallEvent
from .model import World
from .render import (
    BOUNDARY_Y,
    COL_FAIL,
    COL_OK,
    FD_BAR_Y,
    HEIGHT,
    WIDTH,
    Circle,
    Command,
    Line,
    Rect,
    Text,
)

# Extra palette indices (Pyxel default palette).
_COL_KERNEL_BG = 1  # navy backdrop for kernel space
_COL_BOX_BG = 1
_COL_BOX_EDGE = 12  # light blue process box border
_COL_BOUNDARY = 13  # steel grey boundary
_COL_LABEL = 6  # light grey space labels
_COL_TEXT = 7  # white
_COL_DIM = 5  # dark grey
_COL_PULSE = 10  # yellow pulse in flight / waiting
_COL_NAME = 9  # orange syscall name tag

# Layout.
_PROC_X = 88
_PROC_Y = 40
_PROC_W = 80
_PROC_H = 34
_PULSE_X = _PROC_X + _PROC_W // 2
_ORIGIN_Y = _PROC_Y + _PROC_H  # where pulses are born and land back
_REST_Y = 178  # where a blocked pulse waits in kernel space
_FD_SEP_Y = FD_BAR_Y - 8

# Animation timing. Both trips must finish well under the 30-frame budget
# (R3: pulse below boundary within 30 frames of ENTER; R5: nothing left
# below it within 30 frames of EXIT).
_DESCEND_FRAMES = 18
_RETURN_FRAMES = 14
_RING_TTL = 10  # impact rings; far below the 30-frame cap
_FAIL_RESULT_TTL = 30  # frames a failure result lingers before fading (R6)

_BOB = (0, -1, -1, 0, 1, 1)  # idle wobble for a waiting pulse
_DASH = 8  # boundary dash length


class _PulseState(Enum):
    DESCEND = auto()
    WAIT = auto()
    RETURN = auto()


@dataclass
class _Pulse:
    """One in-flight syscall, from ENTER to landing back in userland."""

    name: str
    state: _PulseState = _PulseState.DESCEND
    t: int = 0  # frames spent in the current state
    y: float = float(_ORIGIN_Y)
    return_from: float = float(_REST_Y)
    result: int | None = None


@dataclass
class _Ring:
    """Transient impact ring; expands and dies within _RING_TTL frames."""

    x: int
    y: int
    color: int
    age: int = 0


@dataclass
class Scene:
    """Owns transient visual state (pulses, effects) across frames."""

    _frame: int = 0
    _pulse: _Pulse | None = None
    _rings: list[_Ring] = field(default_factory=list)
    _result_shown_since: int | None = None  # frame the current result landed

    def notify(self, event: SyscallEvent) -> None:
        """React to an event the world just applied."""
        if event.phase is Phase.ENTER:
            self._pulse = _Pulse(name=event.name)
            return
        pulse = self._pulse
        if pulse is None:
            return  # EXIT without an observed ENTER: nothing to animate
        result = event.result if event.result is not None else 0
        pulse.state = _PulseState.RETURN
        pulse.t = 0
        pulse.return_from = pulse.y
        pulse.result = result
        self._rings.append(_Ring(_PULSE_X, int(pulse.y), self._result_color(result)))

    def step(self) -> None:
        """Advance animations by one frame."""
        self._frame += 1
        for ring in self._rings:
            ring.age += 1
        self._rings = [r for r in self._rings if r.age < _RING_TTL]

        pulse = self._pulse
        if pulse is None:
            return
        pulse.t += 1
        if pulse.state is _PulseState.DESCEND:
            before = pulse.y
            progress = min(1.0, pulse.t / _DESCEND_FRAMES)
            pulse.y = _lerp(float(_ORIGIN_Y), float(_REST_Y), _ease(progress))
            if before <= BOUNDARY_Y < pulse.y:
                self._rings.append(_Ring(_PULSE_X, BOUNDARY_Y, _COL_PULSE))
            if progress >= 1.0:
                pulse.state = _PulseState.WAIT
                pulse.t = 0
        elif pulse.state is _PulseState.RETURN:
            progress = min(1.0, pulse.t / _RETURN_FRAMES)
            pulse.y = _lerp(pulse.return_from, float(_ORIGIN_Y), _ease(progress))
            if progress >= 1.0:
                self._rings.append(
                    _Ring(_PULSE_X, _ORIGIN_Y, self._result_color(pulse.result or 0))
                )
                self._pulse = None
                self._result_shown_since = self._frame

    def render(self, world: World) -> list[Command]:
        """Emit the commands for the current frame."""
        commands: list[Command] = []
        self._draw_spaces(commands)
        self._draw_process(commands, world)
        self._draw_result(commands, world)
        self._draw_pulse(commands)
        self._draw_fd_bar(commands, world)
        self._draw_rings(commands)
        return commands

    # -- layers ------------------------------------------------------------

    def _draw_spaces(self, commands: list[Command]) -> None:
        # Kernel space backdrop, dashed boundary (R1), space labels (R2).
        commands.append(Rect(0, BOUNDARY_Y + 1, WIDTH, HEIGHT - BOUNDARY_Y - 1, _COL_KERNEL_BG))
        offset = (self._frame // 4) % (_DASH * 2)
        for x in range(-offset, WIDTH, _DASH * 2):
            x1 = max(0, x)
            x2 = min(WIDTH - 1, x + _DASH - 1)
            if x1 <= x2:
                commands.append(Line(x1, BOUNDARY_Y, x2, BOUNDARY_Y, _COL_BOUNDARY))
        commands.append(Text(5, BOUNDARY_Y - 11, "USERLAND", _COL_LABEL))
        commands.append(Text(5, BOUNDARY_Y + 6, "KERNEL SPACE", _COL_LABEL))

    def _draw_process(self, commands: list[Command], world: World) -> None:
        process = world.process
        commands.append(Rect(_PROC_X, _PROC_Y, _PROC_W, _PROC_H, _COL_BOX_BG))
        commands.append(Rect(_PROC_X, _PROC_Y, _PROC_W, _PROC_H, _COL_BOX_EDGE, filled=False))
        commands.append(Text(_PROC_X + 5, _PROC_Y + 5, process.name, _COL_TEXT))
        commands.append(Text(_PROC_X + 5, _PROC_Y + 13, f"pid {process.pid}", _COL_DIM))
        if process.in_syscall is not None:
            commands.append(Text(_PROC_X + 5, _PROC_Y + 23, f"{process.in_syscall}()", _COL_PULSE))

    def _draw_result(self, commands: list[Command], world: World) -> None:
        # R5/R6: last result as "= {result}" in userland, colored by sign.
        # Held back while the pulse is still riding home so the value visibly
        # arrives with it. A success then persists; a failure fades (R6).
        result = world.process.last_result
        if result is None:
            return
        pulse = self._pulse
        if pulse is not None and pulse.state is _PulseState.RETURN:
            return
        faded = (
            self._result_shown_since is not None
            and self._frame - self._result_shown_since > _FAIL_RESULT_TTL
        )
        if result < 0 and faded:
            return
        color = self._result_color(result)
        commands.append(Text(_PROC_X + _PROC_W + 6, _PROC_Y + 13, f"= {result}", color))

    def _draw_pulse(self, commands: list[Command]) -> None:
        pulse = self._pulse
        if pulse is None:
            return
        y = int(pulse.y)
        if pulse.state is _PulseState.WAIT:
            y += _BOB[(self._frame // 4) % len(_BOB)]
        if pulse.state is _PulseState.RETURN:
            color = self._result_color(pulse.result if pulse.result is not None else 0)
        else:
            color = _COL_PULSE

        # Thread back to the process box, then a short motion trail.
        commands.append(Line(_PULSE_X, _ORIGIN_Y, _PULSE_X, y, _COL_DIM))
        direction = -1 if pulse.state is _PulseState.RETURN else 1
        if pulse.state is not _PulseState.WAIT:
            for k in (1, 2):
                trail_y = y - direction * k * 5
                if _ORIGIN_Y <= trail_y <= _REST_Y:
                    commands.append(Circle(_PULSE_X, trail_y, max(1, 3 - k), _COL_DIM))
        # R6: a failing return is drawn smaller, so it reads as minor.
        radius = 2 if pulse.state is _PulseState.RETURN and (pulse.result or 0) < 0 else 3
        commands.append(Circle(_PULSE_X, y, radius, color))

        # R4: a blocked syscall is named where it waits, below the boundary.
        commands.append(Text(_PULSE_X + 8, y - 2, pulse.name, _COL_NAME))
        if pulse.state is _PulseState.WAIT:
            ripple = 5 + (pulse.t // 3) % 6
            commands.append(Circle(_PULSE_X, y, ripple, _COL_DIM, filled=False))

    def _draw_fd_bar(self, commands: list[Command], world: World) -> None:
        # R7: open fds listed at or below FD_BAR_Y; closed fds vanish.
        commands.append(Line(0, _FD_SEP_Y, WIDTH - 1, _FD_SEP_Y, _COL_DIM))
        commands.append(Text(5, _FD_SEP_Y + 4, "FDS", _COL_LABEL))
        x = 26
        for number in sorted(world.process.fds):
            fd = world.process.fds[number]
            label = f"{fd.number} {fd.target}" if fd.target is not None else f"{fd.number}"
            w = len(label) * 4 + 6
            commands.append(Rect(x, FD_BAR_Y, w, 11, _COL_BOX_EDGE, filled=False))
            commands.append(Text(x + 4, FD_BAR_Y + 3, label, _COL_TEXT))
            x += w + 6

    def _draw_rings(self, commands: list[Command]) -> None:
        for ring in self._rings:
            commands.append(Circle(ring.x, ring.y, 2 + ring.age, ring.color, filled=False))

    @staticmethod
    def _result_color(result: int) -> int:
        return COL_OK if result >= 0 else COL_FAIL


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)  # smoothstep
