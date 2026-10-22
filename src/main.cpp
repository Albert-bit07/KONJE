#include "konje/pipeline.hpp"
#include "konje/profile_store.hpp"
#include "konje/scheduler.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::string home() {
    const char* value = std::getenv("HOME");
    if (!value || !*value) throw std::runtime_error("HOME not configured");
    return value;
}
std::string getenv_or(const char* name, const char* fallback) {
    const char* raw = std::getenv(name);
    return raw && *raw ? raw : fallback;
}
std::vector<std::string> worker_command() {
    const char* script = std::getenv("KONJE_WORKER_PATH");
    if (!script || !*script) return {};
    if (script[0] != '/' || !std::filesystem::is_regular_file(script))
        throw std::runtime_error("KONJE_WORKER_PATH must point to an existing absolute Python script");
    return {"python3", script};
}
void help() {
    std::cout << "KONJE (experimental memory support; NOT clinical software)\n"
              << "Usage:\n"
              << "  konje init-key          Generate a private AES-256 key (never commit it)\n"
              << "  konje enroll ID         Locally enroll one consenting volunteer; 3 captures\n"
              << "  konje revoke ID         Delete a profile from the local encrypted database\n"
              << "  konje list              List opaque enrolled IDs only\n"
              << "  konje run               Interactive request loop: Enter=request, c=cancel, q=quit\n"
              << "Environment: KONJE_CAMERA=none|rpicam|uvc, KONJE_SPEECH=off|on,\n"
              << "  KONJE_WORKER_PATH=/absolute/path/to/recognition_worker.py\n";
}
std::string prompt(const std::string& label) {
    std::cout << label << ": " << std::flush;
    std::string answer;
    if (!std::getline(std::cin, answer) || answer.empty() || answer.size() > 4096)
        throw std::runtime_error("missing or oversized input");
    return answer;
}
void enroll(konje::ProfileStore& store, const std::string& id) {
    auto command = worker_command();
    if (command.empty()) throw std::runtime_error("set KONJE_WORKER_PATH first");
    std::cout << "Only enroll a volunteer who explicitly agreed to face enrollment.\n";
    if (prompt("Type CONSENT CONFIRMED after verifying permission") != "CONSENT CONFIRMED")
        throw std::runtime_error("consent not confirmed");
    konje::Profile p;
    p.id = id;
    p.model_id = getenv_or("KONJE_MODEL_ID", "");
    if (p.model_id.empty() || p.model_id.size() > 128) throw std::runtime_error("set KONJE_MODEL_ID to a stable model/version identifier before enrollment");
    p.name = prompt("Approved display name");
    p.relationship = prompt("Approved relationship");
    p.introduction = prompt("Exact approved spoken introduction (no model generation)");
    std::vector<float> sum;
    std::vector<float> initial;
    for (int i = 0; i < 3; ++i) {
        std::cout << "Enrollment capture " << i + 1 << "/3: keep only one face in frame; press Enter.\n";
        std::string line;
        if (!std::getline(std::cin, line)) throw std::runtime_error("enrollment interrupted");
        auto values = konje::capture_embedding(command, [] { return true; },
                                                getenv_or("KONJE_CAMERA", "none"),
                                                getenv_or("KONJE_UVC_DEVICE", "/dev/video0"));
        if (!values || (i && values->size() != sum.size()))
            throw std::runtime_error("enrollment capture failed; no profile created");
        double norm = 0;
        for (const float value : *values) norm += static_cast<double>(value) * value;
        if (norm < 1e-12) throw std::runtime_error("invalid enrollment embedding");
        norm = std::sqrt(norm);
        for (float& value : *values) value = static_cast<float>(value / norm);
        if (i == 0) { sum.assign(values->size(), 0); initial = *values; }
        else {
            double dot = 0;
            for (std::size_t j = 0; j < values->size(); ++j)
                dot += static_cast<double>((*values)[j]) * initial[j];
            // Conservatively reject wildly inconsistent captures. Not a calibrated threshold.
            if (dot < 0.75) throw std::runtime_error("inconsistent enrollment captures");
        }
        for (std::size_t j = 0; j < sum.size(); ++j) sum[j] += (*values)[j];
    }
    double norm = 0;
    for (const float value : sum) norm += static_cast<double>(value) * value;
    if (norm < 1e-12) throw std::runtime_error("invalid averaged embedding");
    for (float& value : sum) value = static_cast<float>(value / std::sqrt(norm));
    p.embedding = std::move(sum);
    store.put(p);
    std::cout << "Stored encrypted profile ID: " << id << "\n";
}
}
int main(int argc, char** argv) {
    try {
        if (argc < 2 || std::string(argv[1]) == "--help") { help(); return 0; }
        const std::string action(argv[1]);
        const auto config_dir = std::filesystem::path(home()) / ".config" / "konje";
        const auto data_dir = std::filesystem::path(home()) / ".local" / "share" / "konje";
        const auto key = config_dir / "master.key";
        const auto db = data_dir / "profiles.sqlite3";
        if (action == "init-key" && argc == 2) {
            konje::create_key_file(key);
            std::cout << "Key created in private directory (DO NOT commit or disclose).\n";
            return 0;
        }
        konje::ProfileStore store(db, key);
        if (action == "enroll" && argc == 3) { enroll(store, argv[2]); return 0; }
        if (action == "revoke" && argc == 3) {
            store.revoke(argv[2]);
            std::cout << "Local profile revoked. Other offline devices are NOT updated.\n";
            return 0;
        }
        if (action == "list" && argc == 2) {
            for (const auto& p : store.list()) std::cout << p.id << '\n';
            return 0;
        }
        if (action == "run" && argc == 2) {
            konje::PipelineConfig config;
            config.worker_command = worker_command();
            config.policy.model_id = getenv_or("KONJE_MODEL_ID", "");
            config.speak = getenv_or("KONJE_SPEECH", "off") == "on";
            config.camera = getenv_or("KONJE_CAMERA", "none");
            config.uvc_device = getenv_or("KONJE_UVC_DEVICE", "/dev/video0");
            konje::Pipeline pipeline(store, config);
            konje::Scheduler scheduler([&](std::uint64_t id, const konje::Scheduler::Current& current) {
                const auto outcome = pipeline.execute(id, current);
                if (current()) std::cout << "Request #" << id << ": " << outcome.status
                                         << " (" << outcome.detail << ")\n" << std::flush;
            });
            std::cout << "KONJE: Enter=request, c=cancel, q=quit.\n";
            std::string line;
            while (std::getline(std::cin, line)) {
                if (line == "q") break;
                if (line == "c") { scheduler.cancel(); std::cout << "Cancelled\n"; }
                else std::cout << "Request #" << scheduler.submit() << " submitted\n";
            }
            scheduler.shutdown();
            return 0;
        }
        help();
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "KONJE: " << error.what() << '\n';
        return 1;
    }
}