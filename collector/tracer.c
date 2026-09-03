/* fuddy-duddy collector: ptrace syscall tracer.
 *
 * Contract: SPEC.md "Collector wire protocol", enforced by
 * tests/test_tracer.py. Responsibilities: spawn and trace ONE child,
 * discriminate syscall enter/exit, decode registers, read string arguments
 * from child memory, and emit normalized event lines on stderr, flushed
 * per line. Nothing else lives here; names and semantics are Python's job.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/uio.h>

/* PTRACE_GET_SYSCALL_INFO if headers lack it. */
#ifndef PTRACE_GET_SYSCALL_INFO
#define PTRACE_GET_SYSCALL_INFO 0x420e
#endif

#ifndef PTRACE_SYSCALL_INFO_ENTRY
#define PTRACE_SYSCALL_INFO_ENTRY 1
#endif
#ifndef PTRACE_SYSCALL_INFO_EXIT
#define PTRACE_SYSCALL_INFO_EXIT 2
#endif

/* Mirror only the fields we use of struct ptrace_syscall_info to avoid
 * glibc/kernel header conflicts. Layout matches the kernel ABI. */
struct pt_syscall_info {
    uint8_t op;
    uint8_t pad[3];
    uint32_t arch;
    uint64_t instruction_pointer;
    uint64_t stack_pointer;
    union {
        struct {
            uint64_t nr;
            uint64_t args[6];
        } entry;
        struct {
            int64_t rval;
            uint8_t is_error;
        } exit;
    };
};

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* Read a NUL-terminated string from child memory at `addr`. Writes an escaped
 * representation into `out` (size cap). Returns 0 on success, -1 on failure. */
static int read_child_string(pid_t pid, uint64_t addr, char *out, size_t out_cap) {
    if (addr == 0)
        return -1;

    char buf[4096];
    size_t total = 0;
    int done = 0;

    /* Read in page-bounded chunks to avoid crossing unmapped pages. */
    while (total < sizeof(buf) - 1 && !done) {
        uint64_t cur = addr + total;
        size_t page_left = 4096 - (cur & 0xfff);
        size_t want = sizeof(buf) - 1 - total;
        if (want > page_left)
            want = page_left;

        struct iovec local = { .iov_base = buf + total, .iov_len = want };
        struct iovec remote = { .iov_base = (void *)(uintptr_t)cur, .iov_len = want };
        ssize_t got = process_vm_readv(pid, &local, 1, &remote, 1, 0);
        if (got <= 0)
            break;

        for (ssize_t i = 0; i < got; i++) {
            if (buf[total + i] == '\0') {
                done = 1;
                total += (size_t)i;
                break;
            }
        }
        if (!done)
            total += (size_t)got;
    }

    if (total == 0 && !done) {
        /* Nothing readable at all. */
        if (out_cap > 0)
            out[0] = '\0';
        return -1;
    }

    /* Escape into out. */
    static const char hexd[] = "0123456789abcdef";
    size_t o = 0;
    for (size_t i = 0; i < total; i++) {
        unsigned char c = (unsigned char)buf[i];
        if (c < 0x21 || c > 0x7e || c == '%') {
            if (o + 3 >= out_cap)
                break;
            out[o++] = '%';
            out[o++] = hexd[c >> 4];
            out[o++] = hexd[c & 0xf];
        } else {
            if (o + 1 >= out_cap)
                break;
            out[o++] = (char)c;
        }
    }
    out[o] = '\0';
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: tracer CMD [ARGS...]\n");
        return 2;
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        /* Child: request tracing, then exec the target. */
        ptrace(PTRACE_TRACEME, 0, 0, 0);
        execvp(argv[1], &argv[1]);
        perror("execvp");
        _exit(127);
    }

    /* Parent: wait for the initial stop at execve. */
    int status;
    if (waitpid(pid, &status, 0) < 0) {
        perror("waitpid");
        return 1;
    }
    if (WIFEXITED(status))
        return WEXITSTATUS(status);
    if (WIFSIGNALED(status))
        return 128 + WTERMSIG(status);

    ptrace(PTRACE_SETOPTIONS, pid, 0,
           (void *)(PTRACE_O_TRACESYSGOOD | PTRACE_O_EXITKILL));

    /* Kick off the first syscall-stop. */
    if (ptrace(PTRACE_SYSCALL, pid, 0, 0) < 0) {
        perror("ptrace syscall");
        return 1;
    }

    for (;;) {
        if (waitpid(pid, &status, 0) < 0) {
            if (errno == EINTR)
                continue;
            perror("waitpid");
            return 1;
        }

        if (WIFEXITED(status)) {
            int code = WEXITSTATUS(status);
            fprintf(stderr, "EXITED pid=%d ts=%llu code=%d\n",
                    (int)pid, (unsigned long long)now_ns(), code);
            fflush(stderr);
            return code;
        }
        if (WIFSIGNALED(status)) {
            int sig = WTERMSIG(status);
            fprintf(stderr, "SIGNALED pid=%d ts=%llu sig=%d\n",
                    (int)pid, (unsigned long long)now_ns(), sig);
            fflush(stderr);
            return 128 + sig;
        }

        if (WIFSTOPPED(status)) {
            int stopsig = WSTOPSIG(status);
            if (stopsig == (SIGTRAP | 0x80)) {
                /* A syscall enter/exit stop. */
                struct pt_syscall_info info;
                memset(&info, 0, sizeof(info));
                long r = ptrace(PTRACE_GET_SYSCALL_INFO, pid,
                                (void *)sizeof(info), &info);
                if (r > 0) {
                    if (info.op == PTRACE_SYSCALL_INFO_ENTRY) {
                        uint64_t nr = info.entry.nr;
                        char line[8192];
                        int n = snprintf(line, sizeof(line),
                            "ENTER pid=%d ts=%llu nr=%llu args=%llx,%llx,%llx,%llx,%llx,%llx",
                            (int)pid, (unsigned long long)now_ns(),
                            (unsigned long long)nr,
                            (unsigned long long)info.entry.args[0],
                            (unsigned long long)info.entry.args[1],
                            (unsigned long long)info.entry.args[2],
                            (unsigned long long)info.entry.args[3],
                            (unsigned long long)info.entry.args[4],
                            (unsigned long long)info.entry.args[5]);

                        /* Decode openat path (arg index 1). */
                        if (nr == 257 && n > 0 && (size_t)n < sizeof(line)) {
                            char esc[6144];
                            if (read_child_string(pid, info.entry.args[1],
                                                  esc, sizeof(esc)) == 0) {
                                int m = snprintf(line + n, sizeof(line) - (size_t)n,
                                                 " str1=%s", esc);
                                if (m > 0)
                                    n += m;
                            }
                        }
                        fputs(line, stderr);
                        fputc('\n', stderr);
                        fflush(stderr);
                    } else if (info.op == PTRACE_SYSCALL_INFO_EXIT) {
                        fprintf(stderr, "EXIT pid=%d ts=%llu ret=%lld err=%d\n",
                                (int)pid, (unsigned long long)now_ns(),
                                (long long)info.exit.rval,
                                info.exit.is_error ? 1 : 0);
                        fflush(stderr);
                    }
                }
                ptrace(PTRACE_SYSCALL, pid, 0, 0);
            } else if (stopsig == SIGTRAP) {
                /* Non-syscall trap (e.g. event stops); continue quietly. */
                ptrace(PTRACE_SYSCALL, pid, 0, 0);
            } else {
                /* Genuine signal-delivery-stop: inject the signal. */
                ptrace(PTRACE_SYSCALL, pid, 0, (void *)(uintptr_t)stopsig);
            }
        }
    }
}
