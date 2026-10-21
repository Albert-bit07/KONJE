#pragma once
#include <chrono>
#include <cstddef>
#include <functional>
#include <string>
#include <string_view>
#include <vector>

namespace konje {
struct ProcessResult {
    int exit_code{-1};
    std::string output;
    bool cancelled{false};
    bool timed_out{false};
};
// Linux only. No shell. In-memory stdin, bounded stdout, cancellation + deadlines.
ProcessResult run_process(const std::vector<std::string>& argv,
    std::chrono::milliseconds timeout, const std::function<bool()>& still_current,
    std::size_t max_output = 131072, std::string_view input = {});
}