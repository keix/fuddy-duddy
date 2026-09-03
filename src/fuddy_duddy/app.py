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
            self.scene.notify(self.world.apply(event))
        self.scene.step()
        self.frame += 1

    def commands(self) -> list[Command]:
        return self.scene.render(self.world)
