from .event import Phase, SyscallEvent
from .model import Process, World
from .visualizer import Visualizer


def main() -> None:
    world = World(Process(pid=1234, name="cat"))
    # Fake events for now; the strace collector replaces this later.
    script = [
        (30, SyscallEvent(1234, "read", Phase.ENTER)),
        (80, SyscallEvent(1234, "read", Phase.EXIT, 128)),
    ]
    Visualizer(world, script).run()


if __name__ == "__main__":
    main()
