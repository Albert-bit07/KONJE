#include "konje/persistent_client.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

namespace konje {
namespace {
struct Socket {
    int fd{-1};
    ~Socket() { if (fd >= 0) ::close(fd); }
    Socket(const Socket&) = delete;
    Socket& operator=(const Socket&) = delete;
    Socket() = default;
};
void append_u32(std::string& out, std::uint32_t n) {
    for (int shift = 0; shift < 32; shift += 8)
        out.push_back(static_cast<char>((n >> shift) & 255U));
}
// Returns false on cancellation, deadline, disconnected peer or socket failure.
bool ready(int fd, short events, std::chrono::steady_clock::time_point deadline,
           const std::function<bool()>& current) {
    while (current()) {
        const auto left = std::chrono::duration_cast<std::chrono::milliseconds>(
            deadline - std::chrono::steady_clock::now()).count();
        if (left <= 0) return false;
        pollfd p{fd, events, 0};
        const int outcome = poll(&p, 1, static_cast<int>(std::min<std::int64_t>(left, 20)));
        if (outcome < 0 && errno == EINTR) continue;
        if (outcome < 0 || (p.revents & (POLLERR | POLLNVAL))) return false;
        if (outcome > 0 && (p.revents & (events | POLLHUP))) return true;
    }
    return false;
}
bool send_all(int fd, std::string_view bytes, std::chrono::steady_clock::time_point deadline,
              const std::function<bool()>& current) {
    while (!bytes.empty()) {
        if (!ready(fd, POLLOUT, deadline, current)) return false;
        const ssize_t n = send(fd, bytes.data(), bytes.size(), MSG_NOSIGNAL);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) return false;
        bytes.remove_prefix(static_cast<std::size_t>(n));
    }
    return true;
}
bool read_exact(int fd, char* buffer, std::size_t count,
                std::chrono::steady_clock::time_point deadline,
                const std::function<bool()>& current) {
    std::size_t pos = 0;
    while (pos < count) {
        if (!ready(fd, POLLIN, deadline, current)) return false;
        const ssize_t n = recv(fd, buffer + pos, count - pos, 0);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) return false;
        pos += static_cast<std::size_t>(n);
    }
    return true;
}
}
std::optional<std::string> persistent_infer(const std::string& path,
                                             std::string_view identity,
                                             std::string_view burst,
                                             const std::function<bool()>& current,
                                             std::chrono::milliseconds timeout) {
    constexpr std::size_t max_burst = 7 + 3 * (4 + 4 * 1024 * 1024);
    if (!current() || path.empty() || path.size() >= sizeof(sockaddr_un::sun_path) ||
        identity.empty() || identity.size() > 128 || burst.size() < 7 ||
        burst.size() > max_burst || timeout.count() <= 0) return std::nullopt;
    // The socket must be owned by us. The daemon creates it with mode 0600.
    struct stat st{};
    if (lstat(path.c_str(), &st) != 0 || !S_ISSOCK(st.st_mode) ||
        st.st_uid != getuid() || (st.st_mode & 0077)) return std::nullopt;
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    Socket conn;
    conn.fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (conn.fd < 0) return std::nullopt;
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::memcpy(addr.sun_path, path.c_str(), path.size() + 1);
    const int result = connect(conn.fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    if (result < 0) {
        if (errno != EINPROGRESS || !ready(conn.fd, POLLOUT, deadline, current)) return std::nullopt;
        int error = 0;
        socklen_t size = sizeof(error);
        if (getsockopt(conn.fd, SOL_SOCKET, SO_ERROR, &error, &size) != 0 || error) return std::nullopt;
    }
    std::string body;
    body.reserve(2 + identity.size() + burst.size());
    const auto id_len = static_cast<std::uint16_t>(identity.size());
    body.push_back(static_cast<char>(id_len & 255U));
    body.push_back(static_cast<char>((id_len >> 8) & 255U));
    body.append(identity);
    body.append(burst);
    std::string request;
    request.reserve(body.size() + 4);
    append_u32(request, static_cast<std::uint32_t>(body.size()));
    request.append(body);
    if (!send_all(conn.fd, request, deadline, current)) return std::nullopt;
    std::array<unsigned char, 4> header{};
    if (!read_exact(conn.fd, reinterpret_cast<char*>(header.data()), header.size(), deadline, current))
        return std::nullopt;
    std::uint32_t length = 0;
    for (unsigned shift = 0; shift < 32; shift += 8)
        length |= static_cast<std::uint32_t>(header[shift / 8]) << shift;
    if (length == 0 || length > 65536) return std::nullopt;
    std::string reply(length, '\0');
    if (!read_exact(conn.fd, reply.data(), reply.size(), deadline, current) || !current())
        return std::nullopt;
    return reply;
}
}