#pragma once
#include "konje/model.hpp"
#include "konje/profile_store.hpp"
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace konje {
struct PipelineConfig {
    // Worker accepts JPEG bytes on stdin, prints 'EMBEDDING f1 f2 ...' or 'UNCERTAIN'.
    std::vector<std::string> worker_command;
    bool speak{false};
    std::string camera{"none"}; // none (default), rpicam, uvc
    std::string uvc_device{"/dev/video0"};
    MatchPolicy policy{};
};
struct RequestOutcome {
    std::uint64_t id;
    std::string status; // uncertain, recognized, cancelled, unavailable, error
    std::string detail; // Do not include names in logs.
};
class Pipeline {
public:
    Pipeline(ProfileStore& store, PipelineConfig config);
    RequestOutcome execute(std::uint64_t id, const std::function<bool()>& current);
private:
    ProfileStore& store_;
    PipelineConfig config_;
};
std::optional<std::vector<float>> parse_worker_response(const std::string& text);
// No disk frame storage; only returns embedding if worker reports exactly one usable face.
std::optional<std::vector<float>> capture_embedding(
    const std::vector<std::string>& worker_command, const std::function<bool()>& current,
    const std::string& camera, const std::string& uvc_device,
    int burst_frames = 1);
}