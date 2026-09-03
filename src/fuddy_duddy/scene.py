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

from .event import Event, Phase, SpawnEvent
from .model import Process, World
from .render import (
    BOUNDARY_Y,
    COL_FAIL,
    COL_OK,
    FD_BAR_Y,
    HEIGHT,
    WIDTH,
    ZONE_LABELS,
    ZONE_ORDER,
    Circle,
    Command,
    Line,
    Rect,
    Text,
    zone_bounds,
    zone_center,
)
from .results import format_result
from .subsystems import Subsystem, classify

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
_COL_MEM = 3  # dark green memory-region blocks (R10)

# Layout.
_PROC_X = 88
_PROC_Y = 40
_PROC_W = 80
_PROC_H = 34
_PULSE_X = _PROC_X + _PROC_W // 2
_ORIGIN_Y = _PROC_Y + _PROC_H  # where pulses are born and land back

# Multi-box tiling (R12): process boxes tile left-to-right by pid in a row
# across userland, between the R11 status line (y~2) and the boundary.
_ROW_X = 6  # left margin of the box row
_ROW_W = WIDTH - 2 * _ROW_X  # available width for tiled boxes
_BOX_GAP = 6  # horizontal gap between tiled boxes
_MAX_BOX_W = _PROC_W  # a lone box keeps the original single-box width
_REST_Y = 178  # where a blocked pulse waits in kernel space
_FD_SEP_Y = FD_BAR_Y - 8

# Animation timing. Both trips must finish well under the 30-frame budget
# (R3: pulse below boundary within 30 frames of ENTER; R5: nothing left
# below it within 30 frames of EXIT).
_DESCEND_FRAMES = 18
_RETURN_FRAMES = 14
_RING_TTL = 10  # impact rings; far below the 30-frame cap
_FAIL_RESULT_TTL = 30  # frames a failure result lingers before fading (R6)
_STATUS_TTL = 90  # frames the top-of-screen status line lingers (R11)
_SPLIT_TTL = 24  # frames a spawn split flourish lives (R13); settles < 30

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
    target_x: int = _PULSE_X  # zone center this syscall lands over (R9)
    origin_x: int = _PULSE_X  # x of the owning process's box center (SPEC)
    path: str | None = None  # the syscall's path argument, if any (R11)
    fd: int | None = None  # the syscall's fd argument, if any (R11)
    state: _PulseState = _PulseState.DESCEND
    t: int = 0  # frames spent in the current state
    x: float = float(_PULSE_X)
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
class _Split:
    """A spawn flourish (R13): the child's box visibly peels off the parent.

    Purely transient — the boxes themselves come from world state (R12); this
    is the short separation motion. Settles well within the 30-frame budget.
    """

    parent: int
    child: int
    age: int = 0


@dataclass
class Scene:
    """Owns transient visual state (pulses, effects) across frames."""

    _frame: int = 0
    _pulse: _Pulse | None = None
    _rings: list[_Ring] = field(default_factory=list)
    _splits: list[_Split] = field(default_factory=list)
    # pids known at render time, in stable sorted order, so a pid maps to the
    # same box slot for both drawing (R12) and pulse origins (SPEC).
    _pids: tuple[int, ...] = ()
    _result_shown_since: int | None = None  # frame the current result landed
    _status_msg: str | None = None  # latest completed syscall, one line (R11)
    _status_color: int = COL_OK
    _status_since: int = 0

    def notify(self, event: Event) -> None:
        """React to an event the world just applied."""
        if isinstance(event, SpawnEvent):
            # R13: kick off the split flourish. The child's box comes from world
            # state (R12); this animation is the transient separation motion.
            self._splits.append(_Split(parent=event.parent, child=event.child))
            return
        if event.phase is Phase.ENTER:
            origin_x = self._origin_x_for(event.pid)
            self._pulse = _Pulse(
                name=event.name,
                target_x=zone_center(classify(event.name)),
                origin_x=origin_x,
                path=event.path,
                fd=event.fd,
                x=float(origin_x),
            )
            return
        pulse = self._pulse
        if pulse is None:
            return  # EXIT without an observed ENTER: nothing to animate
        result = event.result if event.result is not None else 0
        pulse.state = _PulseState.RETURN
        pulse.t = 0
        pulse.return_from = pulse.y
        pulse.result = result
        self._rings.append(_Ring(int(pulse.x), int(pulse.y), self._result_color(result)))
        # R11: the top status line, refreshed by every completion (success or
        # failure), so it always names the most recent syscall.
        if pulse.path is not None:
            arg = pulse.path
        elif pulse.fd is not None:
            arg = str(pulse.fd)
        else:
            arg = ""
        self._status_msg = f"{pulse.name}({arg}) = {format_result(pulse.name, result)}"
        self._status_color = self._result_color(result)
        self._status_since = self._frame

    def step(self) -> None:
        """Advance animations by one frame."""
        self._frame += 1
        for ring in self._rings:
            ring.age += 1
        self._rings = [r for r in self._rings if r.age < _RING_TTL]
        for split in self._splits:
            split.age += 1
        self._splits = [s for s in self._splits if s.age < _SPLIT_TTL]

        pulse = self._pulse
        if pulse is None:
            return
        pulse.t += 1
        if pulse.state is _PulseState.DESCEND:
            before = pulse.y
            progress = min(1.0, pulse.t / _DESCEND_FRAMES)
            eased = _ease(progress)
            pulse.y = _lerp(float(_ORIGIN_Y), float(_REST_Y), eased)
            # Diagonal descent from the owning process's box toward the syscall's
            # zone center, so the crossing starts at the right box (SPEC) and the
            # waiting pulse's x lands within its zone (R9).
            pulse.x = _lerp(float(pulse.origin_x), float(pulse.target_x), eased)
            if before <= BOUNDARY_Y < pulse.y:
                self._rings.append(_Ring(int(pulse.x), BOUNDARY_Y, _COL_PULSE))
            if progress >= 1.0:
                pulse.x = float(pulse.target_x)
                pulse.state = _PulseState.WAIT
                pulse.t = 0
        elif pulse.state is _PulseState.RETURN:
            progress = min(1.0, pulse.t / _RETURN_FRAMES)
            eased = _ease(progress)
            pulse.y = _lerp(pulse.return_from, float(_ORIGIN_Y), eased)
            pulse.x = _lerp(float(pulse.target_x), float(pulse.origin_x), eased)
            if progress >= 1.0:
                self._rings.append(
                    _Ring(pulse.origin_x, _ORIGIN_Y, self._result_color(pulse.result or 0))
                )
                self._pulse = None
                self._result_shown_since = self._frame

    def render(self, world: World) -> list[Command]:
        """Emit the commands for the current frame."""
        commands: list[Command] = []
        self._draw_spaces(commands)
        self._draw_process(commands, world)
        self._draw_result(commands, world)
        self._draw_regions(commands, world)
        self._draw_pulse(commands)
        self._draw_fd_bar(commands, world)
        self._draw_rings(commands)
        self._draw_status(commands)
        return commands

    def _draw_status(self, commands: list[Command]) -> None:
        # R11: the most recent completed syscall, near the top, fading.
        if self._status_msg is None or self._frame - self._status_since > _STATUS_TTL:
            return
        commands.append(Text(4, 2, self._status_msg[:62], self._status_color))

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
        # Centered headings, so each names its whole half rather than a corner.
        _centered(commands, "USERLAND", BOUNDARY_Y - 11)
        _centered(commands, "KERNEL SPACE", BOUNDARY_Y + 4)
        self._draw_zones(commands)

    def _draw_zones(self, commands: list[Command]) -> None:
        # R9: four subsystem columns below the boundary, each labeled. The
        # active zone (where a pulse is landing) is highlighted brighter.
        active_x = int(self._pulse.target_x) if self._pulse is not None else None
        for sub in ZONE_ORDER:
            x0, w = zone_bounds(sub)
            # A short tick by the label, not a full divider: kernel space reads
            # as one region that the zones subdivide, not four separate columns.
            if x0 > 0:
                commands.append(Line(x0, BOUNDARY_Y + 14, x0, BOUNDARY_Y + 22, _COL_DIM))
            hot = active_x is not None and x0 <= active_x < x0 + w
            color = _COL_NAME if hot else _COL_DIM
            commands.append(Text(x0 + 4, BOUNDARY_Y + 16, ZONE_LABELS[sub], color))

    def _draw_regions(self, commands: list[Command], world: World) -> None:
        # R10: the process's live memory regions drawn as small blocks inside
        # the MEM zone below the boundary. mmap adds a block, munmap removes it.
        # The blocks are gridded in a band well above the FD bar so nothing
        # here strays into the FD-only band at FD_BAR_Y.
        x0, w = zone_bounds(Subsystem.MEMORY)
        block = 6
        gap = 2
        pad = 4
        cols = max(1, (w - 2 * pad) // (block + gap))
        top = BOUNDARY_Y + 24  # below the zone label, above the FD bar band
        for i, start in enumerate(sorted(world.process.regions)):
            row, col = divmod(i, cols)
            bx = x0 + pad + col * (block + gap)
            by = top + row * (block + gap)
            if by + block >= _FD_SEP_Y:  # never intrude on the FD bar band
                break
            commands.append(Rect(bx, by, block, block, _COL_MEM))

    def _draw_process(self, commands: list[Command], world: World) -> None:
        # R12: draw every process in world.processes as a box in userland,
        # tiled left-to-right by pid, each labeled with its name and pid.
        pids = self._box_pids(world)
        self._pids = pids
        for pid in pids:
            process = world.processes[pid]
            x, y, w, h = self._box_rect(pid)
            x += self._split_offset(pid)  # R13: transient separation nudge
            commands.append(Rect(x, y, w, h, _COL_BOX_BG))
            commands.append(Rect(x, y, w, h, _COL_BOX_EDGE, filled=False))
            commands.append(Text(x + 5, y + 5, process.name, _COL_TEXT))
            commands.append(Text(x + 5, y + 13, f"pid {process.pid}", _COL_DIM))
            if process.in_syscall is not None:
                commands.append(Text(x + 5, y + 23, f"{process.in_syscall}()", _COL_PULSE))
            self._draw_threads(commands, process, x, y, w, h)

    def _draw_threads(
        self, commands: list[Command], process: Process, x: int, y: int, w: int, h: int
    ) -> None:
        # R14: one small marker (Circle) per thread, inside the box in userland
        # (y < BOUNDARY_Y), so a clone-thread reads as one box gaining threads.
        if not process.threads:
            return
        marker_y = min(y + h - 5, BOUNDARY_Y - 3)
        step = 6
        cx = x + 6
        for _ in sorted(process.threads):
            if cx > x + w - 4:
                break
            commands.append(Circle(cx, marker_y, 2, _COL_PULSE))
            cx += step

    # -- box layout (R12) --------------------------------------------------

    @staticmethod
    def _box_pids(world: World) -> tuple[int, ...]:
        return tuple(sorted(world.processes))

    def _box_rect(self, pid: int) -> tuple[int, int, int, int]:
        """(x, y, w, h) of pid's box, tiled left-to-right in sorted order."""
        pids = self._pids
        n = len(pids)
        try:
            i = pids.index(pid)
        except ValueError:
            i = 0
            n = max(1, n)
        if n <= 1:
            # A lone process keeps the original single-box placement, so the
            # single-process scene is pixel-stable.
            return _PROC_X, _PROC_Y, _PROC_W, _PROC_H
        slot = (_ROW_W - (n - 1) * _BOX_GAP) // n
        w = max(24, min(_MAX_BOX_W, slot))
        x = _ROW_X + i * (slot + _BOX_GAP)
        return x, _PROC_Y, w, _PROC_H

    def _origin_x_for(self, pid: int) -> int:
        """Map a pid to the center x of its box (SPEC: pulse origin)."""
        x, _, w, _ = self._box_rect(pid)
        return x + w // 2

    def _split_offset(self, pid: int) -> int:
        """Transient horizontal nudge for a box mid-split (R13)."""
        offset = 0
        for split in self._splits:
            frac = 1.0 - split.age / _SPLIT_TTL  # 1 -> 0 as it settles
            if frac <= 0.0:
                continue
            amp = round(6 * frac)
            if pid == split.child:
                offset += amp  # child peels to the right
            elif pid == split.parent:
                offset -= amp  # parent recoils left
        return offset

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
        bx, by, bw, _ = self._box_rect(world.process.pid)
        commands.append(Text(bx + bw + 6, by + 13, f"= {result}", color))

    def _draw_pulse(self, commands: list[Command]) -> None:
        pulse = self._pulse
        if pulse is None:
            return
        x = int(pulse.x)
        y = int(pulse.y)
        if pulse.state is _PulseState.WAIT:
            y += _BOB[(self._frame // 4) % len(_BOB)]
        if pulse.state is _PulseState.RETURN:
            color = self._result_color(pulse.result if pulse.result is not None else 0)
        else:
            color = _COL_PULSE

        # Thread back to the owning process's box, then a short motion trail.
        commands.append(Line(pulse.origin_x, _ORIGIN_Y, x, y, _COL_DIM))
        direction = -1 if pulse.state is _PulseState.RETURN else 1
        if pulse.state is not _PulseState.WAIT:
            for k in (1, 2):
                trail_y = y - direction * k * 5
                if _ORIGIN_Y <= trail_y <= _REST_Y:
                    commands.append(Circle(x, trail_y, max(1, 3 - k), _COL_DIM))
        # R6: a failing return is drawn smaller, so it reads as minor.
        radius = 2 if pulse.state is _PulseState.RETURN and (pulse.result or 0) < 0 else 3
        commands.append(Circle(x, y, radius, color))

        # R4: a blocked syscall is named where it waits, below the boundary.
        commands.append(Text(x + 8, y - 2, pulse.name, _COL_NAME))
        if pulse.state is _PulseState.WAIT:
            ripple = 5 + (pulse.t // 3) % 6
            commands.append(Circle(x, y, ripple, _COL_DIM, filled=False))

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


_CHAR_W = 4  # Pyxel's built-in font is 4px per character.


def _centered(commands: list[Command], text: str, y: int) -> None:
    commands.append(Text((WIDTH - len(text) * _CHAR_W) // 2, y, text, _COL_LABEL))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)  # smoothstep
