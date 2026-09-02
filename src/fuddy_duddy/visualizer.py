"""Pyxel backend: executes render commands. The only module that touches pyxel."""

import pyxel

from .app import App
from .render import FPS, HEIGHT, WIDTH, Circle, Command, Line, Pixel, Rect, Text


class PyxelBackend:
    def __init__(self, app: App) -> None:
        self.app = app

    def run(self) -> None:
        pyxel.init(WIDTH, HEIGHT, title="fuddy-duddy", fps=FPS)
        pyxel.run(self.update, self.draw)

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()
        self.app.step()

    def draw(self) -> None:
        pyxel.cls(pyxel.COLOR_BLACK)
        for command in self.app.commands():
            self.execute(command)

    def execute(self, command: Command) -> None:
        if isinstance(command, Rect):
            draw_rect = pyxel.rect if command.filled else pyxel.rectb
            draw_rect(command.x, command.y, command.w, command.h, command.color)
        elif isinstance(command, Line):
            pyxel.line(command.x1, command.y1, command.x2, command.y2, command.color)
        elif isinstance(command, Circle):
            draw_circle = pyxel.circ if command.filled else pyxel.circb
            draw_circle(command.x, command.y, command.r, command.color)
        elif isinstance(command, Text):
            pyxel.text(command.x, command.y, command.text, command.color)
        elif isinstance(command, Pixel):
            pyxel.pset(command.x, command.y, command.color)
