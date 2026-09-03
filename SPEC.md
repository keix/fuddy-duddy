# fuddy-duddy — Contract Spec

A process/kernel boundary visualizer for Linux. Syscalls are observed;
**state** is modeled; **change** is visualized. This document plus the tests in
`tests/` are the contract. The implementation of `model.World.apply` and
`scene.Scene` is free within it.

## Pipeline

```text
EventSource ──SyscallEvent──▶ World ──state──▶ Scene ──Command──▶ backend
   (source.py)                (model.py)        (scene.py)         (visualizer.py)
```

- `App.step()` runs once per frame: it polls the source, applies each event to
  the world, forwards the applied event to `Scene.notify`, then calls
  `Scene.step()`.
- `Scene.render(world)` may be called at any time and must be pure: same world +
  same internal scene state → same command list. No wall clock, no randomness;
  time only advances through `step()`.
- `scene.py`, `model.py`, `render.py` must not import pyxel. Only
  `visualizer.py` touches it.

## Model semantics (tests/test_model.py)

- **S1** ENTER sets `process.in_syscall` to the syscall name.
- **S2** EXIT clears `in_syscall` and records `result` in `process.last_result`.
- **S3** A successful `openat` (EXIT result >= 0) creates `fds[result]` whose
  `target` is the `path` given at ENTER. The model must pair the EXIT with the
  pending ENTER to do this. Pairing rules: the model keeps a single pending
  ENTER slot and a new ENTER overwrites it; an EXIT pairs only when its name
  matches the pending ENTER's; orphan or mismatched EXITs perform S2
  bookkeeping only. An EXIT with `result=None` is recorded verbatim and never
  creates or removes FDs. (Per-pid pairing is deferred until the world holds
  more than one process.)
- **S4** A failed syscall (result < 0) changes no state other than S2's
  bookkeeping. No FD is created.
- **S5** A successful `close` removes `fds[event.fd]`.
- **S6** Unknown syscalls perform S1/S2 bookkeeping only. They must not raise
  and must not change fds or other state.

## Scene semantics (tests/test_scene.py)

The screen is 256×256 (`render.py` constants). Userland is above `BOUNDARY_Y`,
kernel space below.

- **R1** The boundary is drawn every frame: Rect/Line commands within ±2px of
  `BOUNDARY_Y`.
- **R2** Labels `USERLAND` (above) and `KERNEL SPACE` (below) are drawn every
  frame.
- **R3** Within 30 frames of an ENTER, a pulse (Circle) exists below the
  boundary: the syscall has visibly crossed into the kernel.
- **R4** While a syscall is blocked (ENTER with no EXIT yet), the pulse stays
  below the boundary indefinitely, labeled with the syscall name (Text below
  the boundary).
- **R5** Within 30 frames of an EXIT, no pulse remains below the boundary, and
  the result is shown in userland as `= {result}` with color `COL_OK`.
  Temporal invariant: the result text must never be visible while its pulse is
  still below the boundary — the value arrives with the messenger. Once shown,
  it persists at least until the next ENTER; after that it is free. Once the
  pulse has returned, kernel space holds only static furniture (backdrop,
  boundary, labels, FD bar) — no syscall-specific leftovers of any command
  type, including the syscall name Text.
- **R6** A failed syscall's result also appears in userland in `COL_FAIL`, but
  unlike a success it is *transient*: it fades within a short frame budget
  instead of persisting, and its returning pulse is drawn more faintly. This
  keeps a storm of startup ENOENTs (loader and locale probing, ordinary in any
  real process) from burying the real work, while a successful result still
  persists at least until the next ENTER (R5).
- **R7** While an FD is open, an entry whose Text begins with the fd number
  appears at y >= `FD_BAR_Y`; after close it disappears. The band at
  y >= `FD_BAR_Y` is reserved exclusively for open-FD entries — nothing else
  may draw Text there.
- **R8** Unknown syscalls still cross the boundary (R3 applies). Coverage
  degrades gracefully: unknown names lose semantics, never the crossing.
- Transient effects (impact flashes etc.) are welcome but must die within 30
  frames so R5's "nothing left below the boundary" holds.

Everything else — shapes, colors beyond COL_OK/COL_FAIL, motion curves, extra
decoration — is aesthetic freedom. Tests are topological (which side of the
boundary, when) and must stay that way; do not assert exact coordinates.

## Collector wire protocol (tests/test_wire.py, tests/test_tracer.py)

The C tracer (`collector/tracer.c`) observes one child process via ptrace and
emits normalized events. C owns the OS boundary only: fork/exec, waitpid,
syscall enter/exit discrimination, register decode, reading string arguments
from child memory. Names, semantics and visualization stay in Python.

### Invocation

```text
./tracer CMD [ARGS...]
```

- The tracer spawns CMD, traces it, and emits events on **stderr** (the
  child's stdin/stdout/stderr are left untouched).
- The tracer's exit code mirrors the child's.
- v1 traces a single process: no follow-fork, x86_64 only.

### Event lines

One event per line, UTF-8, **flushed after every line** (blocking-syscall
visualization depends on ENTER arriving while the child is still blocked):

```text
ENTER pid=1234 ts=123456789 nr=257 args=ffffff9c,7f...,0,0,0,0 str1=README.md
EXIT pid=1234 ts=123456999 ret=3 err=0
EXITED pid=1234 ts=123457999 code=0
SIGNALED pid=1234 ts=123457999 sig=9
```

- `pid`, `nr`, `ret`, `code`, `sig` are decimal; `ret` is the raw return value
  (negative errno when `err=1`). `args` are six comma-separated lowercase hex
  values without `0x`. `ts` is CLOCK_MONOTONIC nanoseconds, decimal.
- `str<k>=` attaches the decoded C string behind argument index k. The tracer
  MUST decode the path argument of `openat` (k=1); other syscalls MAY follow.
  Values are escaped: any byte outside `0x21..0x7e`, plus `%`, is written as
  `%xx` (two lowercase hex digits).
- Syscall numbers, not names, cross the wire. Python resolves names via the
  generated `syscalls_x86_64.py` table.
- Ordering: events of one pid are strictly ordered; for a single-threaded
  child, each ENTER is immediately followed by its EXIT (no other lines for
  that pid in between). The stream starts after execve completes (the execve
  itself is not reported) and ends with EXITED or SIGNALED.
- Parsers MUST accept key=value fields in any order after the kind keyword.

`src/fuddy_duddy/wire.py` is the reference parser for this protocol and is
part of the harness, not of the implementation under test.

## Live pipeline: decode and director (tests/test_decode.py, tests/test_director.py)

Wiring the C collector into the visualizer needs two pure Python layers between
the wire parser and the existing `EventSource` seam. Neither imports pyxel.

```text
tracer ──wire lines──▶ wire.parse_line ──▶ Decoder ──SyscallEvent──▶ Director ──poll(frame)──▶ App
```

### Decoder (`decode.py`, tests/test_decode.py)

Turns wire events into `SyscallEvent`s. Stateful: it remembers the pending
ENTER per pid so it can name the matching EXIT.

- **D1** `WireEnter` → one `SyscallEvent`, `Phase.ENTER`, `pid` preserved, name
  resolved through the generated syscall table (an unknown number becomes
  `"sys_<nr>"`). Argument decoding is per syscall: `openat` sets `path` from
  `strings[1]`; fd-first syscalls (`read`, `write`, `close`, and similar) set
  `fd` from `args[0]`.
- **D2** `WireExit` → one `SyscallEvent`, `Phase.EXIT`, `pid` preserved, `name`
  taken from that pid's pending ENTER (fall back to `"?"` if none), `result` =
  `ret` (negative on failure).
- **D3** `WireExited` / `WireSignaled` → no `SyscallEvent` (empty list).
- The public method is `Decoder.push(event: WireEvent) -> list[SyscallEvent]`.

### Director (`director.py`, tests/test_director.py)

An `EventSource` (implements `poll(frame)`) that paces live events onto frames.
**Observation is real-time; display is playback.** It also exposes
`feed(event)` for the collector thread to push observed events.

- **P1** Every fed event is released exactly once, in FIFO order, across
  successive `poll` calls.
- **P2** At most one event is released per frame. Consecutive releases are
  separated by at least a minimum visual gap, so a burst of fast syscalls stays
  watchable — and a release of an ENTER holds longer than that (a larger
  `ENTER_HOLD_FRAMES`), long enough for the pulse it starts to descend fully
  into kernel space before its EXIT is released and sends it back. `poll` is
  called with monotonically non-decreasing frame numbers.
- **P3** `feed` may run on a different thread than `poll`; the Director is
  thread-safe.
- **P4** With nothing fed (or nothing yet due), `poll` returns `[]`.

### CLI

- `python -m fuddy_duddy` → the looping scripted demo (unchanged).
- `python -m fuddy_duddy -- CMD ARGS...` → live: trace CMD through the C tracer
  and visualize it. Requires `make -C collector` first.

## Gates

```bash
make -C collector  # C build; -Wall -Wextra -Werror is the C lint gate
pytest -q          # semantic contract (builds the collector for its tests)
ruff check src tests
mypy src
```

All must pass. `python -m fuddy_duddy` must then play the scripted
`cat README.md` story: openat → read → write → close, looping.
