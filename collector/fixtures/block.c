/* Deterministic fixture child: blocks forever on read(0) until fed a byte.
 * tests/test_tracer.py uses this to prove the tracer emits (and flushes)
 * ENTER while the child is still inside the syscall.
 */
#include <sys/syscall.h>
#include <unistd.h>

int main(void) {
    char c;
    syscall(SYS_read, 0, &c, 1);
    syscall(SYS_exit_group, 0);
    return 0; /* unreachable */
}
