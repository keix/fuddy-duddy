/* Deterministic fixture child: fork, then the child execve's /bin/true while
 * the parent waits. tests/test_tracer.py uses this to prove the tracer follows
 * the fork — emitting a SPAWN and the child's own events under a second pid.
 */
#include <sys/syscall.h>
#include <unistd.h>

int main(void) {
    long pid = syscall(SYS_fork);
    if (pid == 0) {
        char *const argv[] = {"/bin/true", 0};
        char *const envp[] = {0};
        syscall(SYS_execve, "/bin/true", argv, envp);
        syscall(SYS_exit_group, 1); /* only if execve failed */
    }
    syscall(SYS_wait4, pid, 0, 0, 0);
    syscall(SYS_exit_group, 0);
    return 0; /* unreachable */
}
