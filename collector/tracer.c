/* fuddy-duddy collector: ptrace syscall tracer.
 *
 * Contract: SPEC.md "Collector wire protocol", enforced by
 * tests/test_tracer.py. Responsibilities: spawn and trace ONE child,
 * discriminate syscall enter/exit, decode registers, read string arguments
 * from child memory, and emit normalized event lines on stderr, flushed
 * per line. Nothing else lives here; names and semantics are Python's job.
 */
#include <stdio.h>

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    fprintf(stderr, "tracer: not implemented\n");
    return 3;
}
