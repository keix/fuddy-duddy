"""Visual state machine: turns world state and events into render commands.

The contract is SPEC.md rules R1-R8, enforced by tests/test_scene.py.
This module must not import pyxel; it emits render.Command values only.
"""

from .event import SyscallEvent
from .model import World
from .render import Command


class Scene:
    """Owns transient visual state (pulses, effects) across frames."""

    def notify(self, event: SyscallEvent) -> None:
        """React to an event the world just applied."""
        raise NotImplementedError

    def step(self) -> None:
        """Advance animations by one frame."""
        raise NotImplementedError

    def render(self, world: World) -> list[Command]:
        """Emit the commands for the current frame."""
        raise NotImplementedError
