from .app import App
from .event import Phase, SyscallEvent
from .model import Process, World
from .scene import Scene
from .source import ScriptedSource
from .visualizer import PyxelBackend

PID = 1234

# The story of `cat README.md`, faked. The strace collector replaces this.
SCRIPT = [
    (30, SyscallEvent(PID, "openat", Phase.ENTER, path="README.md")),
    (45, SyscallEvent(PID, "openat", Phase.EXIT, result=3)),
    (70, SyscallEvent(PID, "read", Phase.ENTER, fd=3)),
    (110, SyscallEvent(PID, "read", Phase.EXIT, result=128)),
    (130, SyscallEvent(PID, "write", Phase.ENTER, fd=1)),
    (150, SyscallEvent(PID, "write", Phase.EXIT, result=128)),
    (170, SyscallEvent(PID, "close", Phase.ENTER, fd=3)),
    (180, SyscallEvent(PID, "close", Phase.EXIT, result=0)),
]


def main() -> None:
    world = World(Process(pid=PID, name="cat"))
    app = App(world, Scene(), ScriptedSource(SCRIPT, loop=True))
    PyxelBackend(app).run()


if __name__ == "__main__":
    main()
