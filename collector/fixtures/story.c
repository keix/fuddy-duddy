/* Deterministic fixture child: the cat story in raw syscalls.
 * Usage: story FILE  — opens FILE, reads it, writes it to stdout, closes it,
 * fails to open a missing path, then exits. tests/test_tracer.py asserts
 * this sequence appears in the tracer's event stream.
 */
#include <fcntl.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2)
        return 2;
    char buf[64];
    long fd = syscall(SYS_openat, AT_FDCWD, argv[1], O_RDONLY);
    long n = syscall(SYS_read, fd, buf, sizeof buf);
    syscall(SYS_write, 1, buf, n);
    syscall(SYS_close, fd);
    syscall(SYS_openat, AT_FDCWD, "/fuddy-duddy-missing", O_RDONLY);
    syscall(SYS_exit_group, 0);
    return 0; /* unreachable */
}
