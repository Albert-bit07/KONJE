#pragma once
#include <chrono>
#include <functional>
#include <optional>
#include <string>
#include <string_view>

namespace konje {
// Owner-only UNIX socket. All operations deadline-bound and cancellation-aware.
// Returns no result on unavailable, timed-out, malformed, or superseded requests.
std::optional<std::string> persistent_infer(
    const std::string& socket_path,
    std::string_view model_id,
    std::string_view jpeg_burst,
    const std::function<bool()>& still_current,
    std::chrono::milliseconds timeout = std::chrono::seconds(45));
}