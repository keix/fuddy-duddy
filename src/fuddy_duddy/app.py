from .event import SyscallEvent
from .model import World
from .render import Command
from .scene import Scene
from .source import EventSource


class App:
    """Glue: one step() per frame pulls due events through world into scene."""

    def __init__(self, world: World, scene: Scene, source: EventSource) -> None:
        self.world = world
        self.scene = scene
        self.source = source
        self.frame = 0

    def step(self) -> None:
        for event in self.source.poll(self.frame):
            applied = self.world.apply(event)
            # The scene animates syscalls; SpawnEvent updates only the world
            # (Phase 2). Phase 3 will let the scene react to spawns too.
            if isinstance(applied, SyscallEvent):
                self.scene.notify(applied)
        self.scene.step()
        self.frame += 1

    def commands(self) -> list[Command]:
        return self.scene.render(self.world)
