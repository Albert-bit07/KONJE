#include "konje/pipeline.hpp"
#include "konje/policy.hpp"
#include "konje/process.hpp"

#include <chrono>
#include <cmath>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace konje {
std::optional<std::vector<float>> parse_worker_response(const std::string& text) {
    if (text == "UNCERTAIN\n" || text == "UNCERTAIN") return std::nullopt;
    std::istringstream stream(text);
    std::string marker;
    stream >> marker;
    if (marker != "EMBEDDING") return std::nullopt;
    std::vector<float> values;
    float value{};
    while (stream >> value) {
        if (!std::isfinite(value) || values.size() == 4096) return std::nullopt;
        values.push_back(value);
    }
    if (!stream.eof() || values.empty()) return std::nullopt;
    return values;
}
std::optional<std::vector<float>> capture_embedding(
    const std::vector<std::string>& worker_command, const std::function<bool()>& current,
    const std::string& camera, const std::string& uvc_device,
    int burst_frames) {
    if (worker_command.empty() || !current()) return std::nullopt;
    if (camera == "none" || !current()) return std::nullopt;
    if (burst_frames < 1 || burst_frames > 3) throw std::invalid_argument("burst must be 1..3 frames");
    std::vector<std::string> capture_args;
    if (camera == "rpicam") {
        capture_args = {"rpicam-still", "--nopreview", "--immediate", "--timeout", "500",
                        "--width", "640", "--height", "480", "--encoding", "jpg", "-o", "-"};
    } else if (camera == "uvc") {
        // USB camera frames go from V4L2 to stdout; never create a JPEG on disk.
        capture_args = {"ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-f", "video4linux2",
                        "-i", uvc_device, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"};
    } else {
        throw std::invalid_argument("KONJE_CAMERA must be none, rpicam, or uvc");
    }
    // Framed in-memory protocol: 6-byte magic "KONJE1", one-byte count,
    // then for each frame a little-endian uint32 length and exact JPEG bytes.
    // At most 3 * 4 MiB are retained temporarily; no camera data goes to disk.
    std::string payload = "KONJE1";
    payload.push_back(static_cast<char>(burst_frames));
    for (int i = 0; i < burst_frames && current(); ++i) {
        const auto captured = run_process(capture_args, std::chrono::seconds(8), current, 4 * 1024 * 1024);
        if (!current() || captured.cancelled || captured.exit_code != 0 || captured.timed_out ||
            captured.output.size() < 4 || captured.output.size() > 4 * 1024 * 1024 ||
            static_cast<unsigned char>(captured.output[0]) != 0xff ||
            static_cast<unsigned char>(captured.output[1]) != 0xd8 ||
            static_cast<unsigned char>(captured.output[captured.output.size() - 2]) != 0xff ||
            static_cast<unsigned char>(captured.output.back()) != 0xd9) return std::nullopt;
        const std::uint32_t length = static_cast<std::uint32_t>(captured.output.size());
        for (int k = 0; k < 4; ++k) payload.push_back(static_cast<char>((length >> (k * 8)) & 255U));
        payload.append(captured.output);
    }
    if (!current()) return std::nullopt;
    const auto result = run_process(worker_command, std::chrono::seconds(45), current,
                                    64 * 1024, payload);
    if (!current() || result.cancelled || result.exit_code != 0 || result.timed_out) return std::nullopt;
    return parse_worker_response(result.output);
}
Pipeline::Pipeline(ProfileStore& store, PipelineConfig config)
    : store_(store), config_(std::move(config)) {}
RequestOutcome Pipeline::execute(std::uint64_t id, const std::function<bool()>& current) {
    if (!current()) return {id, "cancelled", "superseded before capture"};
    if (config_.worker_command.empty()) return {id, "unavailable", "inference worker not configured"};
    if (config_.camera == "none") return {id, "unavailable", "camera not enabled"};
    const auto embedding = capture_embedding(config_.worker_command, current,
                                             config_.camera, config_.uvc_device, 3);
    if (!current()) return {id, "cancelled", "superseded during capture or inference"};
    if (!embedding) return {id, "uncertain", "camera or single-face inference unavailable"};
    const auto profiles = store_.list(); // Fresh read; a revocation does not persist in memory as a stale cache.
    const auto match = decide_match(*embedding, profiles, config_.policy);
    if (!current()) return {id, "cancelled", "superseded before recognition"};
    if (match.id.empty()) return {id, "uncertain", match.reason};
    if (!config_.speak) return {id, "recognized", "speech disabled"};
    // Just-in-time recheck for local revocation. Does not guarantee a global distributed
    // revocation barrier; that is a separate feature with acknowledged device versions.
    const auto latest = store_.list();
    for (const auto& profile : latest) {
        if (profile.id == match.id) {
            if (!current()) return {id, "cancelled", "superseded before speech"};
            // A revocation or change to approved speech while TTS is running
            // cancels its process. This is best-effort local enforcement, not
            // a strict barrier across offline replicas or already-played sound.
            const auto still_authorized = [&]() {
                if (!current()) return false;
                try {
                    const auto active = store_.list();
                    for (const auto& item : active) {
                        if (item.id == profile.id && item.model_id == profile.model_id &&
                            item.introduction == profile.introduction) return true;
                    }
                } catch (...) {
                    // Storage/authentication errors must never authorize speech.
                }
                return false;
            };
            if (!still_authorized())
                return {id, "uncertain", "profile revoked or updated before speech"};
            const auto spoken = run_process({"espeak-ng", "--stdin"}, std::chrono::seconds(12),
                                            still_authorized, 4096, profile.introduction);
            if (!current()) return {id, "cancelled", "superseded during speech"};
            if (spoken.cancelled) return {id, "uncertain", "profile revoked or changed during speech"};
            if (spoken.exit_code != 0 || spoken.timed_out) return {id, "unavailable", "speech unavailable"};
            return {id, "recognized", "approved introduction spoken"};
        }
    }
    return {id, "uncertain", "profile revoked before speech"};
}
}