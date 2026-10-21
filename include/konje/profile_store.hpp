#pragma once
#include "konje/model.hpp"
#include <filesystem>
#include <vector>

struct sqlite3;
namespace konje {
// SQLite metadata + per-row AES-256-GCM encrypted payloads. Key is separate.
// A key file is never generated implicitly when opening the database.
void create_key_file(const std::filesystem::path& path);
class ProfileStore {
public:
    ProfileStore(const std::filesystem::path& db_path,
                 const std::filesystem::path& key_path);
    ~ProfileStore();
    ProfileStore(const ProfileStore&) = delete;
    ProfileStore& operator=(const ProfileStore&) = delete;
    void put(const Profile& profile);
    void revoke(const std::string& id);
    std::vector<Profile> list() const;
private:
    sqlite3* db_{nullptr};
    std::vector<unsigned char> key_;
};
}