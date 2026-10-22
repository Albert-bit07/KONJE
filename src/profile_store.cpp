#include "konje/profile_store.hpp"

#include <array>
#include <cerrno>
#include <cmath>
#include <cstring>
#include <fcntl.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <sqlite3.h>
#include <stdexcept>
#include <string_view>
#include <sys/stat.h>
#include <unistd.h>

namespace konje {
namespace {
void secure_parent(const std::filesystem::path& path) {
    const auto parent = path.parent_path();
    if (parent.empty()) throw std::runtime_error("use an absolute path for secure data");
    if (!std::filesystem::exists(parent)) {
        std::filesystem::create_directories(parent);
        if (::chmod(parent.c_str(), 0700) != 0) throw std::runtime_error("cannot secure data directory");
    }
    struct stat st{};
    if (lstat(parent.c_str(), &st) != 0 || !S_ISDIR(st.st_mode) ||
        st.st_uid != getuid() || (st.st_mode & 0077) != 0)
        throw std::runtime_error("private data directory must be owned by this user and mode 0700");
}
void exec(sqlite3* db, const char* sql) {
    char* error = nullptr;
    if (sqlite3_exec(db, sql, nullptr, nullptr, &error) != SQLITE_OK) {
        const std::string message = error ? error : "sqlite error";
        sqlite3_free(error);
        throw std::runtime_error(message);
    }
}
void append_u32(std::string& out, std::uint32_t value) {
    for (int i = 0; i < 4; ++i) out.push_back(static_cast<char>((value >> (i * 8)) & 255U));
}
std::uint32_t read_u32(std::string_view data, std::size_t& cursor) {
    if (data.size() - cursor < 4) throw std::runtime_error("corrupt profile length");
    std::uint32_t value = 0;
    for (int i = 0; i < 4; ++i) value |= static_cast<std::uint32_t>(static_cast<unsigned char>(data[cursor++])) << (i * 8);
    return value;
}
void append_string(std::string& out, const std::string& value) {
    if (value.size() > 4096) throw std::invalid_argument("profile field too long");
    append_u32(out, static_cast<std::uint32_t>(value.size()));
    out.append(value);
}
std::string read_string(std::string_view data, std::size_t& cursor) {
    const auto len = read_u32(data, cursor);
    if (len > 4096 || len > data.size() - cursor) throw std::runtime_error("corrupt profile string");
    std::string value(data.substr(cursor, len));
    cursor += len;
    return value;
}
std::string pack(const Profile& p) {
    if (p.id.empty() || p.id.size() > 128 || p.name.empty() || p.relationship.empty() ||
        p.introduction.empty() || p.embedding.empty() || p.embedding.size() > 4096 ||
        p.model_id.empty() || p.model_id.size() > 128) {
        throw std::invalid_argument("invalid or incomplete consented profile");
    }
    std::string data;
    append_u32(data, 2); // Version 1 had no embedding model identity; never silently upgrade.
    append_string(data, p.name);
    append_string(data, p.relationship);
    append_string(data, p.introduction);
    append_string(data, p.model_id);
    append_u32(data, static_cast<std::uint32_t>(p.embedding.size()));
    for (float value : p.embedding) {
        if (!std::isfinite(value)) throw std::invalid_argument("nonfinite embedding");
        std::uint32_t bits;
        std::memcpy(&bits, &value, 4);
        append_u32(data, bits);
    }
    return data;
}
Profile unpack(std::string_view data, const std::string& id) {
    std::size_t pos = 0;
    if (read_u32(data, pos) != 2) throw std::runtime_error("legacy or unsupported profile schema: reenroll with explicit model ID");
    Profile p;
    p.id = id;
    p.name = read_string(data, pos);
    p.relationship = read_string(data, pos);
    p.introduction = read_string(data, pos);
    p.model_id = read_string(data, pos);
    if (p.model_id.empty() || p.model_id.size() > 128) throw std::runtime_error("invalid enrolled embedding model ID");
    const auto count = read_u32(data, pos);
    if (count == 0 || count > 4096 || count > (data.size() - pos) / 4) throw std::runtime_error("corrupt embedding");
    p.embedding.reserve(count);
    for (std::uint32_t i = 0; i < count; ++i) {
        const std::uint32_t bits = read_u32(data, pos);
        float value;
        std::memcpy(&value, &bits, 4);
        if (!std::isfinite(value)) throw std::runtime_error("nonfinite stored embedding");
        p.embedding.push_back(value);
    }
    if (pos != data.size()) throw std::runtime_error("trailing data in encrypted profile");
    return p;
}
using Block = std::vector<unsigned char>;
struct Sealed { Block nonce, encrypted, tag; };
Sealed seal(const Block& key, const std::string& id, std::string_view plain) {
    Sealed out{Block(12), Block(plain.size() + 16), Block(16)};
    if (RAND_bytes(out.nonce.data(), static_cast<int>(out.nonce.size())) != 1) throw std::runtime_error("random generation failed");
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) throw std::runtime_error("cipher allocation failed");
    int n = 0, total = 0;
    const bool ok = EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1 &&
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, nullptr) == 1 &&
        EVP_EncryptInit_ex(ctx, nullptr, nullptr, key.data(), out.nonce.data()) == 1 &&
        EVP_EncryptUpdate(ctx, nullptr, &n, reinterpret_cast<const unsigned char*>(id.data()), static_cast<int>(id.size())) == 1 &&
        EVP_EncryptUpdate(ctx, out.encrypted.data(), &n, reinterpret_cast<const unsigned char*>(plain.data()), static_cast<int>(plain.size())) == 1;
    if (ok) total = n;
    bool final_ok = ok && EVP_EncryptFinal_ex(ctx, out.encrypted.data() + total, &n) == 1;
    if (final_ok) total += n;
    final_ok = final_ok && EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, out.tag.data()) == 1;
    EVP_CIPHER_CTX_free(ctx);
    if (!final_ok) throw std::runtime_error("encryption failed");
    out.encrypted.resize(static_cast<std::size_t>(total));
    return out;
}
std::string unseal(const Block& key, const std::string& id, const void* nonce, int nonce_size,
                   const void* ciphertext, int len, const void* tag, int tag_size) {
    if (nonce_size != 12 || tag_size != 16 || len < 0 || len > 100000) throw std::runtime_error("invalid encrypted profile");
    std::string out(static_cast<std::size_t>(len) + 16, '\0');
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) throw std::runtime_error("cipher allocation failed");
    int n = 0, total = 0;
    const bool ok = EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1 &&
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, nullptr) == 1 &&
        EVP_DecryptInit_ex(ctx, nullptr, nullptr, key.data(), static_cast<const unsigned char*>(nonce)) == 1 &&
        EVP_DecryptUpdate(ctx, nullptr, &n, reinterpret_cast<const unsigned char*>(id.data()), static_cast<int>(id.size())) == 1 &&
        EVP_DecryptUpdate(ctx, reinterpret_cast<unsigned char*>(out.data()), &n, static_cast<const unsigned char*>(ciphertext), len) == 1;
    if (ok) total = n;
    bool valid = ok && EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, 16, const_cast<void*>(tag)) == 1 &&
        EVP_DecryptFinal_ex(ctx, reinterpret_cast<unsigned char*>(out.data()) + total, &n) == 1;
    EVP_CIPHER_CTX_free(ctx);
    if (!valid) throw std::runtime_error("profile authentication failed; refusing to use data");
    out.resize(static_cast<std::size_t>(total + n));
    return out;
}
struct Statement {
    sqlite3_stmt* value;
    Statement(sqlite3* db, const char* sql) : value(nullptr) {
        if (sqlite3_prepare_v2(db, sql, -1, &value, nullptr) != SQLITE_OK) throw std::runtime_error(sqlite3_errmsg(db));
    }
    ~Statement() { sqlite3_finalize(value); }
};
void bind_blob(sqlite3_stmt* s, int index, const Block& bytes) {
    if (sqlite3_bind_blob(s, index, bytes.data(), static_cast<int>(bytes.size()), SQLITE_TRANSIENT) != SQLITE_OK)
        throw std::runtime_error("sqlite bind failed");
}
}
void create_key_file(const std::filesystem::path& path) {
    secure_parent(path);
    std::array<unsigned char, 32> key{};
    if (RAND_bytes(key.data(), static_cast<int>(key.size())) != 1) throw std::runtime_error("key generation failed");
    const int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (fd < 0) throw std::runtime_error("key exists or cannot be created");
    const ssize_t bytes = write(fd, key.data(), key.size());
    const int closed = close(fd);
    OPENSSL_cleanse(key.data(), key.size());
    if (bytes != 32 || closed != 0) { std::filesystem::remove(path); throw std::runtime_error("could not write complete key"); }
}
ProfileStore::ProfileStore(const std::filesystem::path& db_path, const std::filesystem::path& key_path) {
    struct stat st{};
    if (lstat(key_path.c_str(), &st) != 0 || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
        (st.st_mode & 0077) != 0 || st.st_size != 32)
        throw std::runtime_error("secure 32-byte key missing; run 'konje init-key' first");
    const int fd = open(key_path.c_str(), O_RDONLY | O_NOFOLLOW);
    if (fd < 0) throw std::runtime_error("cannot read key file");
    key_.resize(32);
    const ssize_t n = read(fd, key_.data(), key_.size());
    close(fd);
    if (n != 32) throw std::runtime_error("short key read");
    secure_parent(db_path);
    if (lstat(db_path.c_str(), &st) == 0 &&
        (!S_ISREG(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 0077) != 0))
        throw std::runtime_error("database must be regular file, owned by user, mode 0600");
    // Create securely before SQLite opens it; never briefly expose plaintext metadata.
    if (lstat(db_path.c_str(), &st) != 0) {
        if (errno != ENOENT) throw std::runtime_error("cannot inspect database path");
        const int created = open(db_path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
        if (created < 0) throw std::runtime_error("cannot create private database");
        close(created);
    }
    if (sqlite3_open_v2(db_path.c_str(), &db_, SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX, nullptr) != SQLITE_OK) {
        std::string err = db_ ? sqlite3_errmsg(db_) : "sqlite open failed";
        if (db_) sqlite3_close(db_);
        db_ = nullptr;
        throw std::runtime_error(err);
    }
    try {
        ::chmod(db_path.c_str(), 0600);
        sqlite3_busy_timeout(db_, 1000);
        exec(db_, "PRAGMA secure_delete=ON; PRAGMA temp_store=MEMORY; PRAGMA journal_mode=DELETE;");
        exec(db_, "CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, nonce BLOB NOT NULL, payload BLOB NOT NULL, tag BLOB NOT NULL);");
    } catch (...) { sqlite3_close(db_); db_ = nullptr; throw; }
}
ProfileStore::~ProfileStore() {
    if (db_) sqlite3_close(db_);
    if (!key_.empty()) OPENSSL_cleanse(key_.data(), key_.size());
}
void ProfileStore::put(const Profile& profile) {
    if (profile.id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != std::string::npos)
        throw std::invalid_argument("person ID must be an opaque alphanumeric identifier");
    const std::string plain = pack(profile);
    const Sealed sealed = seal(key_, profile.id, plain);
    Statement s(db_, "INSERT INTO profiles (id,nonce,payload,tag) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET nonce=excluded.nonce,payload=excluded.payload,tag=excluded.tag");
    sqlite3_bind_text(s.value, 1, profile.id.c_str(), -1, SQLITE_TRANSIENT);
    bind_blob(s.value, 2, sealed.nonce);
    bind_blob(s.value, 3, sealed.encrypted);
    bind_blob(s.value, 4, sealed.tag);
    if (sqlite3_step(s.value) != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
}
void ProfileStore::revoke(const std::string& id) {
    Statement s(db_, "DELETE FROM profiles WHERE id=?");
    sqlite3_bind_text(s.value, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(s.value) != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
    if (sqlite3_changes(db_) == 0) throw std::runtime_error("profile not found");
    // SQLite secure_delete attempts to overwrite deleted content; flash storage may retain old cells.
}
std::vector<Profile> ProfileStore::list() const {
    Statement s(db_, "SELECT id, nonce, payload, tag FROM profiles ORDER BY id");
    std::vector<Profile> profiles;
    int status;
    while ((status = sqlite3_step(s.value)) == SQLITE_ROW) {
        const auto* id = reinterpret_cast<const char*>(sqlite3_column_text(s.value, 0));
        if (!id) throw std::runtime_error("invalid stored ID");
        const std::string plain = unseal(key_, id,
            sqlite3_column_blob(s.value, 1), sqlite3_column_bytes(s.value, 1),
            sqlite3_column_blob(s.value, 2), sqlite3_column_bytes(s.value, 2),
            sqlite3_column_blob(s.value, 3), sqlite3_column_bytes(s.value, 3));
        profiles.push_back(unpack(plain, id));
    }
    if (status != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
    return profiles;
}
}