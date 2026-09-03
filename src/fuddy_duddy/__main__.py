import os
import sys

from .app import App
from .director import Director
from .event import Event, Phase, SpawnEvent, SyscallEvent
from .live import LiveCollector
from .model import Process, World
from .scene import Scene
from .source import ScriptedSource
from .visualizer import PyxelBackend

SHELL = 1234
CHILD = 1235

# A faked story of `sh` forking a child that becomes `ls`: the shell reads its
# input, forks (the box splits), the child execve's into ls, and ls does its
# file work. Paced so the structural moments — fork and execve — are legible.
SCRIPT: list[tuple[int, Event]] = [
    (20, SyscallEvent(SHELL, "openat", Phase.ENTER, path="/etc/profile")),
    (35, SyscallEvent(SHELL, "openat", Phase.EXIT, result=3)),
    (55, SyscallEvent(SHELL, "read", Phase.ENTER, fd=3)),
    (75, SyscallEvent(SHELL, "read", Phase.EXIT, result=64)),
    (95, SyscallEvent(SHELL, "fork", Phase.ENTER)),
    (120, SyscallEvent(SHELL, "fork", Phase.EXIT, result=CHILD)),
    (124, SpawnEvent(parent=SHELL, child=CHILD)),  # the box splits
    (150, SyscallEvent(CHILD, "execve", Phase.ENTER, path="/bin/ls")),
    (175, SyscallEvent(CHILD, "execve", Phase.EXIT, result=0)),  # child becomes ls
    (200, SyscallEvent(CHILD, "openat", Phase.ENTER, path=".")),
    (220, SyscallEvent(CHILD, "openat", Phase.EXIT, result=3)),
    (240, SyscallEvent(CHILD, "getdents64", Phase.ENTER, fd=3)),
    (265, SyscallEvent(CHILD, "getdents64", Phase.EXIT, result=512)),
    (285, SyscallEvent(CHILD, "write", Phase.ENTER, fd=1)),
    (305, SyscallEvent(CHILD, "write", Phase.EXIT, result=512)),
    (325, SyscallEvent(SHELL, "wait4", Phase.ENTER)),
    (345, SyscallEvent(SHELL, "wait4", Phase.EXIT, result=CHILD)),
]


def run_demo() -> None:
    world = World(Process(pid=SHELL, name="sh"))
    app = App(world, Scene(), ScriptedSource(SCRIPT, loop=True, loop_pause=60))
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
