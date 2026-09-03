import os
import sys

from .app import App
from .director import Director
from .event import Phase, SyscallEvent
from .live import LiveCollector
from .model import Process, World
from .scene import Scene
from .source import ScriptedSource
from .visualizer import PyxelBackend

DEMO_PID = 1234

# The story of `cat README.md`, faked, for the no-argument demo.
SCRIPT = [
    (30, SyscallEvent(DEMO_PID, "openat", Phase.ENTER, path="README.md")),
    (45, SyscallEvent(DEMO_PID, "openat", Phase.EXIT, result=3)),
    (70, SyscallEvent(DEMO_PID, "read", Phase.ENTER, fd=3)),
    (110, SyscallEvent(DEMO_PID, "read", Phase.EXIT, result=128)),
    (130, SyscallEvent(DEMO_PID, "write", Phase.ENTER, fd=1)),
    (150, SyscallEvent(DEMO_PID, "write", Phase.EXIT, result=128)),
    (170, SyscallEvent(DEMO_PID, "close", Phase.ENTER, fd=3)),
    (180, SyscallEvent(DEMO_PID, "close", Phase.EXIT, result=0)),
]


def run_demo() -> None:
    world = World(Process(pid=DEMO_PID, name="cat"))
    app = App(world, Scene(), ScriptedSource(SCRIPT, loop=True))
    PyxelBackend(app).run()


def run_live(cmd: list[str]) -> None:
    world = World(Process(pid=0, name=os.path.basename(cmd[0])))
    director = Director()
    collector = LiveCollector(cmd, director)
    app = App(world, Scene(), director)
    collector.start()
    try:
        PyxelBackend(app).run()
    finally:
        collector.stop()


def main() -> None:
    argv = sys.argv[1:]
    if "--" in argv:
        cmd = argv[argv.index("--") + 1 :]
        if not cmd:
            sys.exit("usage: python -m fuddy_duddy -- CMD [ARGS...]")
        run_live(cmd)
    else:
        run_demo()


if __name__ == "__main__":
    main()
