from collections import deque

import pyxel

from .event import Phase, SyscallEvent
from .model import World

WIDTH = 256
HEIGHT = 256
FPS = 30

BOUNDARY_Y = 128
KERNEL_Y = 184  # where a pulse lands

PROC_W = 40
PROC_H = 20
PROC_X = (WIDTH - PROC_W) // 2
PROC_Y = 56

PULSE_SPEED = 3
LOOP_PAUSE = 45  # frames to hold the final state before replaying

COL_KERNEL_BG = pyxel.COLOR_NAVY
COL_BOUNDARY = pyxel.COLOR_LIGHT_BLUE
COL_LABEL = pyxel.COLOR_GRAY
COL_TRAIL = pyxel.COLOR_DARK_BLUE


class Ripple:
    """Expanding ring marking an impact on either side of the boundary."""

    def __init__(self, x: int, y: int, color: int) -> None:
        self.x = x
        self.y = y
        self.color = color
        self.age = 0
        self.ttl = 12

    @property
    def alive(self) -> bool:
        return self.age < self.ttl

    def update(self) -> None:
        self.age += 1

    def draw(self) -> None:
        pyxel.circb(self.x, self.y, 2 + self.age, self.color)


class Pulse:
    """A syscall crossing the boundary: down into the kernel and back."""

    DOWN, WAIT, UP, DONE = range(4)

    def __init__(self, name: str) -> None:
        self.name = name
        self.state = Pulse.DOWN
        self.x = PROC_X + PROC_W // 2
        self.y = PROC_Y + PROC_H
        self.result: int | None = None
        self.exit_seen = False
        self.trail: deque[int] = deque(maxlen=8)

    def finish(self, result: int | None) -> None:
        self.result = result
        self.exit_seen = True

    def update(self) -> str | None:
        """Advance one frame; returns "landed" / "returned" on transitions."""
        transition = None
        if self.state in (Pulse.DOWN, Pulse.UP):
            self.trail.append(self.y)
        if self.state == Pulse.DOWN:
            self.y += PULSE_SPEED
            if self.y >= KERNEL_Y:
                self.y = KERNEL_Y
                self.state = Pulse.WAIT
                self.trail.clear()
                transition = "landed"
        if self.state == Pulse.WAIT and self.exit_seen:
            self.state = Pulse.UP
        if self.state == Pulse.UP:
            self.y -= PULSE_SPEED
            if self.y <= PROC_Y + PROC_H:
                self.state = Pulse.DONE
                transition = "returned"
        return transition

    @property
    def failed(self) -> bool:
        return self.result is not None and self.result < 0

    @property
    def color(self) -> int:
        if self.state == Pulse.UP:
            return pyxel.COLOR_RED if self.failed else pyxel.COLOR_LIME
        return pyxel.COLOR_WHITE

    def draw(self) -> None:
        if self.state == Pulse.DONE:
            return
        for i, ty in enumerate(self.trail):
            color = self.color if i >= len(self.trail) - 2 else COL_TRAIL
            pyxel.pset(self.x, ty, color)
        radius = 2
        if self.state == Pulse.WAIT:
            radius = 2 + (pyxel.frame_count // 4) % 2
        pyxel.circ(self.x, self.y, radius, self.color)
        if self.state == Pulse.WAIT:
            pyxel.text(self.x + 8, self.y - 2, self.name, pyxel.COLOR_YELLOW)


class Visualizer:
    """Plays a scripted list of (frame, event) pairs against the world."""

    def __init__(self, world: World, script: list[tuple[int, SyscallEvent]]) -> None:
        self.world = world
        self.script = script
        self.frame = 0
        self.index = 0
        self.pulse: Pulse | None = None
        self.ripples: list[Ripple] = []
        self.proc_flash = 0

    def run(self) -> None:
        pyxel.init(WIDTH, HEIGHT, title="fuddy-duddy", fps=FPS)
        pyxel.run(self.update, self.draw)

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()
        while self.index < len(self.script) and self.frame >= self.script[self.index][0]:
            event = self.world.apply(self.script[self.index][1])
            self.dispatch(event)
            self.index += 1
        if self.pulse is not None:
            transition = self.pulse.update()
            if transition == "landed":
                self.ripples.append(Ripple(self.pulse.x, KERNEL_Y, pyxel.COLOR_CYAN))
            elif transition == "returned":
                self.proc_flash = 8
                self.ripples.append(
                    Ripple(self.pulse.x, PROC_Y + PROC_H, self.pulse.color)
                )
        for ripple in self.ripples:
            ripple.update()
        self.ripples = [r for r in self.ripples if r.alive]
        if self.proc_flash > 0:
            self.proc_flash -= 1
        self.frame += 1
        if self.finished() and self.frame >= self.script[-1][0] + LOOP_PAUSE:
            self.restart()

    def dispatch(self, event: SyscallEvent) -> None:
        if event.phase is Phase.ENTER:
            self.pulse = Pulse(event.name)
        elif self.pulse is not None:
            self.pulse.finish(event.result)

    def finished(self) -> bool:
        return self.index >= len(self.script) and (
            self.pulse is None or self.pulse.state == Pulse.DONE
        )

    def restart(self) -> None:
        self.frame = 0
        self.index = 0
        self.pulse = None
        self.ripples = []
        self.proc_flash = 0
        self.world.process.in_syscall = None
        self.world.process.last_result = None

    def draw(self) -> None:
        pyxel.cls(pyxel.COLOR_BLACK)
        pyxel.rect(0, BOUNDARY_Y + 1, WIDTH, HEIGHT - BOUNDARY_Y, COL_KERNEL_BG)
        self.draw_boundary()
        for ripple in self.ripples:
            ripple.draw()
        if self.pulse is not None:
            self.pulse.draw()
        self.draw_process()

    def draw_boundary(self) -> None:
        pyxel.text(8, 8, "USERLAND", COL_LABEL)
        offset = (pyxel.frame_count // 6) % 12
        for x in range(offset - 12, WIDTH, 12):
            pyxel.rect(x, BOUNDARY_Y - 1, 7, 2, COL_BOUNDARY)
        pyxel.text(8, BOUNDARY_Y + 6, "KERNEL SPACE", COL_LABEL)

    def draw_process(self) -> None:
        proc = self.world.process
        border = pyxel.COLOR_WHITE
        if self.proc_flash > 0 and self.pulse is not None:
            border = self.pulse.color
        pyxel.rect(PROC_X, PROC_Y, PROC_W, PROC_H, pyxel.COLOR_BLACK)
        pyxel.rectb(PROC_X, PROC_Y, PROC_W, PROC_H, border)
        pyxel.text(PROC_X + 4, PROC_Y + 3, str(proc.pid), COL_LABEL)
        pyxel.text(PROC_X + 4, PROC_Y + 11, proc.name, pyxel.COLOR_WHITE)
        if proc.in_syscall is not None:
            pyxel.text(PROC_X + PROC_W + 6, PROC_Y + 11, proc.in_syscall, pyxel.COLOR_YELLOW)
        elif proc.last_result is not None:
            pyxel.text(
                PROC_X + PROC_W + 6,
                PROC_Y + 11,
                f"= {proc.last_result}",
                pyxel.COLOR_RED if proc.last_result < 0 else pyxel.COLOR_LIME,
            )
