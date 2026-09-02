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
- **R6** A failed syscall's result text uses `COL_FAIL` instead.
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

## Gates

```bash
pytest -q          # semantic contract
ruff check src tests
mypy src
```

All three must pass. `python -m fuddy_duddy` must then play the scripted
`cat README.md` story: openat → read → write → close, looping.
