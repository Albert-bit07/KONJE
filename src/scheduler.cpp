#include "konje/scheduler.hpp"
#include <exception>
#include <iostream>
#include <stdexcept>

namespace konje {
Scheduler::Scheduler(Work work) : work_(std::move(work)), worker_(&Scheduler::loop, this) {}
Scheduler::~Scheduler() { shutdown(); }
std::uint64_t Scheduler::submit() {
    std::lock_guard lock(mutex_);
    if (stopping_) throw std::runtime_error("scheduler stopped");
    const auto id = ++generation_;
    pending_ = id; // Supersede any unprocessed request; never grow an unbounded queue.
    cv_.notify_one();
    return id;
}
void Scheduler::cancel() {
    std::lock_guard lock(mutex_);
    ++generation_;
    pending_.reset();
    cv_.notify_all();
}
bool Scheduler::current(std::uint64_t id) const {
    std::lock_guard lock(mutex_);
    return !stopping_ && id == generation_;
}
void Scheduler::shutdown() {
    {
        std::lock_guard lock(mutex_);
        stopping_ = true;
        ++generation_;
        pending_.reset();
        cv_.notify_all();
    }
    if (worker_.joinable()) worker_.join();
}
void Scheduler::loop() {
    while (true) {
        std::uint64_t id;
        {
            std::unique_lock lock(mutex_);
            cv_.wait(lock, [&] { return stopping_ || pending_.has_value(); });
            if (stopping_) return;
            id = *pending_;
            pending_.reset();
        }
        try {
            work_(id, [this, id] { return current(id); });
        } catch (const std::exception& ex) {
            if (current(id)) std::cerr << "Request " << id << " failed: " << ex.what() << '\n';
        } catch (...) {
            if (current(id)) std::cerr << "Request " << id << " failed (unknown error)\n";
        }
    }
}
}