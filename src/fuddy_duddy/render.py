"""Render command IR: the contract between Scene and any backend.

This module must not import pyxel. Colors are Pyxel palette indices (0-15)
so the backend can pass them through unchanged.
"""

from dataclasses import dataclass

from .subsystems import Subsystem

WIDTH = 256
HEIGHT = 256
FPS = 75  # frame-based pacing is unchanged; a higher fps just plays it faster

BOUNDARY_Y = 128  # the user/kernel boundary
FD_BAR_Y = 232    # open file descriptors are listed at or below this line

COL_OK = 11    # lime  — successful syscall results
COL_FAIL = 8   # red   — failed syscall results

# Kernel space is split into four subsystem columns below the boundary (R9).
# OTHER has no column of its own; it targets the center of kernel space.
ZONE_ORDER = (Subsystem.FILE, Subsystem.MEMORY, Subsystem.PROCESS, Subsystem.NET)
ZONE_LABELS = {
    Subsystem.FILE: "FILE",
    Subsystem.MEMORY: "MEM",
    Subsystem.PROCESS: "PROC",
    Subsystem.NET: "NET",
}
ZONE_W = WIDTH // 4


def zone_bounds(sub: Subsystem) -> tuple[int, int]:
    """(x, width) of a subsystem's column; OTHER spans the whole width."""
    if sub in ZONE_ORDER:
        return ZONE_ORDER.index(sub) * ZONE_W, ZONE_W
    return 0, WIDTH


def zone_center(sub: Subsystem) -> int:
    x, w = zone_bounds(sub)
    return x + w // 2


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int
    color: int
    filled: bool = True


@dataclass(frozen=True)
class Line:
    x1: int
    y1: int
    x2: int
    y2: int
    color: int


@dataclass(frozen=True)
class Circle:
    x: int
    y: int
    r: int
    color: int
    filled: bool = True


@dataclass(frozen=True)
class Text:
    x: int
    y: int
    text: str
    color: int


@dataclass(frozen=True)
class Pixel:
    x: int
    y: int
    color: int


Command = Rect | Line | Circle | Text | Pixel
