#pragma once
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>
#include <thread>

namespace konje {
// Latest-request-wins. Only one active task and one pending request (bounded).
class Scheduler {
public:
    using Current = std::function<bool()>;
    using Work = std::function<void(std::uint64_t, const Current&)>;
    explicit Scheduler(Work work);
    ~Scheduler();
    Scheduler(const Scheduler&) = delete;
    Scheduler& operator=(const Scheduler&) = delete;
    std::uint64_t submit();
    void cancel();
    void shutdown();
    bool current(std::uint64_t id) const;
private:
    void loop();
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::optional<std::uint64_t> pending_;
    std::uint64_t generation_{0};
    bool stopping_{false};
    Work work_;
    std::thread worker_;
};
}