#include "konje/process.hpp"

#include <array>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <spawn.h>
#include <stdexcept>
#include <string_view>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;
namespace konje {
namespace {
struct Fd {
    int value{-1};
    explicit Fd(int v = -1) : value(v) {}
    ~Fd() { if (value >= 0) close(value); }
    Fd(const Fd&) = delete;
    Fd& operator=(const Fd&) = delete;
};
void write_all(int fd, std::string_view bytes) {
    while (!bytes.empty()) {
        const ssize_t n = write(fd, bytes.data(), bytes.size());
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) throw std::runtime_error("writing child input failed");
        bytes.remove_prefix(static_cast<std::size_t>(n));
    }
}
void terminate(pid_t pid, int& status) {
    kill(-pid, SIGKILL); // The child starts a new process group.
    kill(pid, SIGKILL);
    while (waitpid(pid, &status, 0) == -1 && errno == EINTR) {}
}
}
ProcessResult run_process(const std::vector<std::string>& argv,
                          std::chrono::milliseconds timeout,
                          const std::function<bool()>& still_current,
                          std::size_t max_output,
                          std::string_view input) {
    if (argv.empty() || argv.front().empty() || timeout.count() <= 0 || max_output == 0)
        throw std::invalid_argument("invalid subprocess arguments");
    if (!still_current()) {
        ProcessResult result;
        result.cancelled = true;
        return result;
    }
    int pipes[2];
    // The parent reads nonblocking, but the child's stdout MUST stay blocking.
    // Making both pipe ends nonblocking loses larger JPEG/model outputs with EAGAIN.
    if (pipe2(pipes, O_CLOEXEC) != 0) throw std::runtime_error("pipe failed");
    Fd read_end(pipes[0]);
    Fd write_end(pipes[1]);
    const int flags = fcntl(read_end.value, F_GETFL);
    if (flags < 0 || fcntl(read_end.value, F_SETFL, flags | O_NONBLOCK) < 0)
        throw std::runtime_error("cannot configure nonblocking parent pipe");
    // Linux anonymous in-memory file: no JPEGs, embeddings or speech text on disk.
    Fd input_fd(memfd_create("konje-child-input", MFD_CLOEXEC));
    if (input_fd.value < 0) throw std::runtime_error("memfd creation failed");
    write_all(input_fd.value, input);
    if (lseek(input_fd.value, 0, SEEK_SET) < 0) throw std::runtime_error("input rewind failed");

    posix_spawn_file_actions_t actions;
    posix_spawnattr_t attributes;
    if (posix_spawn_file_actions_init(&actions) != 0) throw std::runtime_error("spawn actions failed");
    if (posix_spawnattr_init(&attributes) != 0) {
        posix_spawn_file_actions_destroy(&actions);
        throw std::runtime_error("spawn attrs failed");
    }
    posix_spawn_file_actions_adddup2(&actions, input_fd.value, STDIN_FILENO);
    posix_spawn_file_actions_adddup2(&actions, write_end.value, STDOUT_FILENO);
    posix_spawn_file_actions_addopen(&actions, STDERR_FILENO, "/dev/null", O_WRONLY, 0);
    posix_spawn_file_actions_addclose(&actions, read_end.value);
    posix_spawn_file_actions_addclose(&actions, write_end.value);
    posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETPGROUP);
    posix_spawnattr_setpgroup(&attributes, 0);
    std::vector<char*> args;
    for (const auto& arg : argv) args.push_back(const_cast<char*>(arg.c_str()));
    args.push_back(nullptr);
    pid_t pid = -1;
    const int rc = posix_spawnp(&pid, argv[0].c_str(), &actions, &attributes, args.data(), environ);
    posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attributes);
    if (rc != 0) throw std::runtime_error("could not start executable: " + argv[0]);
    close(write_end.value);
    write_end.value = -1;

    ProcessResult result;
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    int status = 0;
    bool child_exited = false, eof = false;
    while (!(child_exited && eof)) {
        if (!child_exited) {
            const pid_t waited = waitpid(pid, &status, WNOHANG);
            if (waited == pid) child_exited = true;
            else if (waited == -1) { terminate(pid, status); throw std::runtime_error("waitpid failed"); }
        }
        if (!still_current()) result.cancelled = true;
        if (std::chrono::steady_clock::now() >= deadline) result.timed_out = true;
        if (result.cancelled || result.timed_out) {
            if (!child_exited) terminate(pid, status);
            else kill(-pid, SIGKILL); // Clean up surviving descendants of an exited wrapper.
            child_exited = true;
            break;
        }
        std::array<char, 8192> buffer{};
        for (;;) {
            const auto n = read(read_end.value, buffer.data(), buffer.size());
            if (n > 0) {
                if (static_cast<std::size_t>(n) > max_output - result.output.size()) {
                    result.timed_out = true; // Hard output-size limit.
                    kill(-pid, SIGKILL); // Stop descendants even if the wrapper already exited.
                    if (!child_exited) terminate(pid, status);
                    child_exited = true;
                    break;
                }
                result.output.append(buffer.data(), static_cast<std::size_t>(n));
            } else if (n == 0) { eof = true; break; }
            else if (errno == EINTR) continue;
            else if (errno == EAGAIN) break;
            else { if (!child_exited) terminate(pid, status); throw std::runtime_error("reading child failed"); }
        }
        if (result.timed_out || (child_exited && eof)) break;
        pollfd pfd{read_end.value, static_cast<short>(POLLIN | POLLHUP), 0};
        (void)poll(&pfd, 1, 15);
    }
    if (WIFEXITED(status) && !result.cancelled && !result.timed_out)
        result.exit_code = WEXITSTATUS(status);
    return result;
}
}