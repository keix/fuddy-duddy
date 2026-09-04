from fuddy_duddy.app import App
from fuddy_duddy.event import ExitEvent, Phase, SpawnEvent, SyscallEvent
from fuddy_duddy.model import Process, World
from fuddy_duddy.render import Circle, Command, Text
from fuddy_duddy.scene import Scene
from fuddy_duddy.source import ScriptedSource

PID = 1234


def enter(name: str, pid: int = PID, **kwargs: object) -> SyscallEvent:
    return SyscallEvent(pid, name, Phase.ENTER, **kwargs)  # type: ignore[arg-type]


def exited(name: str, result: int, pid: int = PID, **kwargs: object) -> SyscallEvent:
    return SyscallEvent(pid, name, Phase.EXIT, result=result, **kwargs)  # type: ignore[arg-type]


def spawn(child: int, parent: int = PID) -> SpawnEvent:
    return SpawnEvent(parent=parent, child=child)


def died(pid: int, code: int = 0) -> ExitEvent:
    return ExitEvent(pid=pid, code=code)


def make_world() -> World:
    return World(Process(pid=PID, name="cat"))


def make_app(script: list[tuple[int, SyscallEvent]]) -> App:
    return App(make_world(), Scene(), ScriptedSource(script))


def run_frames(script: list[tuple[int, SyscallEvent]], frames: int) -> list[Command]:
    """Drive a fresh app for `frames` frames and return the final frame's commands."""
    app = make_app(script)
    for _ in range(frames):
        app.step()
    return app.commands()


def circles(commands: list[Command]) -> list[Circle]:
    return [c for c in commands if isinstance(c, Circle)]


def texts(commands: list[Command]) -> list[Text]:
    return [c for c in commands if isinstance(c, Text)]
