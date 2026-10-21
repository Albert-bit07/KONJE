#include "konje/pipeline.hpp"
#include "konje/policy.hpp"
#include "konje/process.hpp"
#include "konje/profile_store.hpp"
#include "konje/scheduler.hpp"
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
#include <sqlite3.h>

using namespace std::chrono_literals;
namespace {
void must(bool p, const char* msg) { if (!p) throw std::runtime_error(msg); }
template <class F> void rejects(F&& fn) {
    bool rejected = false;
    try { fn(); } catch (const std::exception&) { rejected = true; }
    must(rejected, "expected rejection");
}
struct TempDir {
    std::filesystem::path path;
    TempDir() {
        char name[] = "/tmp/konje-test-XXXXXX";
        char* value = mkdtemp(name);
        if (!value) throw std::runtime_error("mkdtemp failed");
        path = value;
    }
    ~TempDir() { std::filesystem::remove_all(path); }
};
void policy_tests() {
    const konje::Profile a{"opaque_a", "Sample A", "friend", "Approved A", {1, 0, 0}};
    const konje::Profile b{"opaque_b", "Sample B", "friend", "Approved B", {0, 1, 0}};
    const auto rule = konje::MatchPolicy{.minimum_similarity = 0.6F, .minimum_margin = 0.10F};
    must(konje::decide_match({1, 0, 0}, {a, b}, rule).id == "opaque_a", "expected match");
    must(konje::decide_match({0, 0, 0}, {a, b}, rule).id.empty(), "zero vector must be uncertain");
    must(konje::decide_match({0, 0, 1}, {a, b}, rule).id.empty(), "unknown must be uncertain");
    must(konje::decide_match({1, 0, 0}, {a, a}, rule).id.empty(), "duplicate identity must be uncertain");
    const konje::Profile close{"opaque_c", "C", "friend", "Approved", {0.99F, 0.1F, 0}};
    must(konje::decide_match({1, 0, 0}, {a, close}, rule).id.empty(), "near-tie must be uncertain");
    must(konje::decide_match({std::numeric_limits<float>::quiet_NaN()}, {a}, rule).id.empty(), "NaN fail closed");
    rejects([&] { konje::decide_match({1}, {a}, {.minimum_similarity = 2, .minimum_margin = 0}); });
}
void encrypted_store_tests() {
    TempDir tmp;
    const auto cfg = tmp.path / "keys";
    const auto data = tmp.path / "data";
    const auto key = cfg / "secret.key";
    const auto db = data / "profiles.db";
    rejects([&] { konje::ProfileStore missing(db, key); });
    konje::create_key_file(key);
    rejects([&] { konje::create_key_file(key); });
    konje::Profile sample{"person_1", "Volunteer One", "friend", "Hello, this is Volunteer One.", {1, 0}};
    {
        konje::ProfileStore store(db, key);
        store.put(sample);
        auto loaded = store.list();
        must(loaded.size() == 1 && loaded[0].introduction == sample.introduction, "encrypted roundtrip");
        sample.introduction = "Approved updated introduction.";
        store.put(sample);
        must(store.list()[0].introduction == sample.introduction, "update");
    }
    {
        std::ifstream f(db, std::ios::binary);
        std::string bytes((std::istreambuf_iterator<char>(f)), {});
        must(bytes.find("Approved updated introduction.") == std::string::npos, "stored plaintext leaked");
        must(bytes.find("Volunteer One") == std::string::npos, "stored name leaked");
    }
    {
        konje::ProfileStore store(db, key);
        store.revoke("person_1");
        must(store.list().empty(), "revocation must remove active profile");
        rejects([&] { store.revoke("person_1"); });
        store.put(sample);
    }
    sqlite3* raw{};
    must(sqlite3_open(db.c_str(), &raw) == SQLITE_OK, "tamper test open");
    must(sqlite3_exec(raw, "UPDATE profiles SET tag=zeroblob(16)", nullptr, nullptr, nullptr) == SQLITE_OK, "tamper SQL");
    sqlite3_close(raw);
    konje::ProfileStore store(db, key);
    rejects([&] { (void)store.list(); });
}
void subprocess_tests() {
    const auto bytes = std::string("abc\0def", 7);
    const auto cat = konje::run_process({"cat"}, 1000ms, [] { return true; }, 64, bytes);
    must(cat.exit_code == 0 && cat.output == bytes, "binary pipe roundtrip");
    const auto timed = konje::run_process({"sleep", "2"}, 40ms, [] { return true; });
    must(timed.timed_out, "timeout must kill child");
    const auto bounded = konje::run_process({"yes"}, 3000ms, [] { return true; }, 64);
    must(bounded.timed_out && bounded.output.size() <= 64, "output must be bounded");
    const auto cancelled = konje::run_process({"sleep", "2"}, 3000ms, [] { return false; });
    must(cancelled.cancelled, "pre-start cancel");
}
void scheduler_tests() {
    std::mutex mu;
    std::condition_variable cv;
    std::atomic<int> entered{0};
    std::atomic<int> completed{0};
    konje::Scheduler scheduler([&](std::uint64_t id, const konje::Scheduler::Current& current) {
        ++entered;
        cv.notify_all();
        if (id == 1) {
            std::unique_lock lk(mu);
            cv.wait_for(lk, 500ms, [&] { return !current(); });
        }
        if (current()) completed = static_cast<int>(id);
    });
    must(scheduler.submit() == 1, "first id");
    {
        std::unique_lock lk(mu);
        must(cv.wait_for(lk, 1s, [&] { return entered == 1; }), "first task entered");
    }
    must(scheduler.submit() == 2, "second id");
    must(scheduler.submit() == 3, "third id");
    {
        std::unique_lock lk(mu);
        must(cv.wait_for(lk, 1s, [&] { return entered >= 2; }), "last task started");
    }
    scheduler.shutdown();
    // 2 was overwritten; 1 was superseded; 3 may finish before shutdown depending on scheduling.
    must(entered == 2, "bounded queue, middle request discarded");
    must(completed == 0 || completed == 3, "superseded task never commits");
}
void worker_protocol_tests() {
    must(!konje::parse_worker_response("UNCERTAIN\n"), "uncertain result");
    must(!konje::parse_worker_response("EMBEDDING nan"), "bad float");
    must(!konje::parse_worker_response("MATCH person_A"), "untrusted identity from worker");
    must(!konje::parse_worker_response("EMBEDDING 1 2 garbage"), "trailing garbage");
    auto good = konje::parse_worker_response("EMBEDDING 1 0.1 -0.5\n");
    must(good && good->size() == 3, "well-formed embedding");
}
}
int main() {
    try {
        policy_tests();
        encrypted_store_tests();
        subprocess_tests();
        scheduler_tests();
        worker_protocol_tests();
        std::cout << "KONJE: all local core tests passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "KONJE test failure: " << e.what() << '\n';
        return 1;
    }
}