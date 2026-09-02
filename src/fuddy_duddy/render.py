"""Render command IR: the contract between Scene and any backend.

This module must not import pyxel. Colors are Pyxel palette indices (0-15)
so the backend can pass them through unchanged.
"""

from dataclasses import dataclass

WIDTH = 256
HEIGHT = 256
FPS = 30

BOUNDARY_Y = 128  # the user/kernel boundary
FD_BAR_Y = 232    # open file descriptors are listed at or below this line

COL_OK = 11    # lime  — successful syscall results
COL_FAIL = 8   # red   — failed syscall results


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
