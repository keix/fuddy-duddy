"""Live collector: runs the C tracer and feeds decoded events to a Director.

This is the I/O wiring around the pure decode/director layers: it spawns the
tracer as a subprocess and pumps its stderr on a background thread. The child's
own stdout/stderr pass through to the terminal.
"""

import subprocess
import threading
from pathlib import Path

from .decode import Decoder
from .director import Director
from .wire import parse_line

TRACER = Path(__file__).resolve().parent.parent.parent / "collector" / "tracer"


class LiveCollector:
    def __init__(self, cmd: list[str], director: Director) -> None:
        self.cmd = cmd
        self.director = director
        self.decoder = Decoder()
        self.proc: subprocess.Popen[str] | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if not TRACER.exists():
            raise FileNotFoundError(f"tracer not built; run `make -C collector` (missing {TRACER})")
        self.proc = subprocess.Popen(
            [str(TRACER), *self.cmd],
            stderr=subprocess.PIPE,
            text=True,
        )
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            line = line.strip()
            if not line:
                continue
            try:
                wire = parse_line(line)
            except ValueError:
                continue  # a diagnostic line, not an event
            for event in self.decoder.push(wire):
                self.director.feed(event)

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
