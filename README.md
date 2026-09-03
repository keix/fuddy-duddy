# Fuddy-Duddy
A system call visualizer for Linux.

## Why Fuddy-Duddy?

Modern software is often built on layers of abstractions.

Frameworks sit on runtimes. Runtimes sit on libraries. Libraries sit on operating systems. As more attention moves toward the surface, the machinery underneath becomes easier to forget.

But some boundaries remain.

A process still enters the kernel through a system call. File descriptors still refer to kernel-managed objects. `read`, `write`, `mmap`, `fork`, and `exec` still describe fundamental interactions between a program and the operating system.

Fuddy-Duddy looks at that old, stubbornly persistent layer and renders it in 8-bit form.

The implementation, however, is deliberately modern.

The system is divided by explicit contracts, in the same spirit that makes POSIX useful: each boundary defines what crosses it and what the other side is allowed to assume.

Tracing, events, state, and visualization are separate concerns. Their interfaces are kept small and explicit.

Once those boundaries are established, the remaining implementation is delegated to Ralph and driven by the harness.

- The human defines the contracts
- The harness defines correctness
- Ralph fills in the implementation

Nothing exists between boundaries unless it has to.

## Usage

The development environment is provided by Nix. Everything below runs inside it:

```sh
nix develop          # Python + strace + the SDL libraries Pyxel needs
make -C collector    # build the C tracer for live tracing
```

Run the visualizer:

```sh
python -m fuddy_duddy                    # looping scripted demo
python -m fuddy_duddy -- cat README.md   # trace a real command
```

A process begins in Userland, crosses the user/kernel boundary through a system
call, and reaches the subsystem it touches: FILE, MEM, PROC, or NET.

The return path is shown in green on success and red on failure.

Press `Q` or `Esc` to quit.

## License
Copyright Kei Sawamura 2026.

Fuddy-Duddy is licensed under the MIT License, following Pyxel, on which it is
built. Copying and modifying is encouraged and appreciated.
