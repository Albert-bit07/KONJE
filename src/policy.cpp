#include "konje/policy.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace konje {
namespace {
float similarity(const std::vector<float>& a, const std::vector<float>& b) {
    if (a.empty() || a.size() != b.size()) return -2.0F;
    double dot = 0.0, an = 0.0, bn = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (!std::isfinite(a[i]) || !std::isfinite(b[i])) return -2.0F;
        dot += static_cast<double>(a[i]) * b[i];
        an += static_cast<double>(a[i]) * a[i];
        bn += static_cast<double>(b[i]) * b[i];
    }
    if (an < 1e-12 || bn < 1e-12) return -2.0F;
    return static_cast<float>(dot / std::sqrt(an * bn));
}
}
MatchResult decide_match(const std::vector<float>& candidate,
                         const std::vector<Profile>& enrolled,
                         MatchPolicy policy) {
    if (candidate.empty()) return {"", "no usable embedding"};
    if (policy.model_id.empty()) return {"", "embedding model not configured"};
    if (!(policy.minimum_similarity >= -1.0F && policy.minimum_similarity <= 1.0F) ||
        !(policy.minimum_margin >= 0.0F && policy.minimum_margin <= 2.0F)) {
        throw std::invalid_argument("invalid recognition policy settings");
    }
    float best = -2.0F;
    float second = -2.0F;
    std::string best_id;
    std::unordered_set<std::string> ids;
    for (const Profile& item : enrolled) {
        if (item.id.empty() || !ids.insert(item.id).second) return {"", "ambiguous directory"};
        if (item.model_id != policy.model_id) return {"", "incompatible enrolled embedding model"};
        const float score = similarity(candidate, item.embedding);
        if (score > best) {
            second = best;
            best = score;
            best_id = item.id;
        } else if (score > second) {
            second = score;
        }
    }
    if (best_id.empty() || best < policy.minimum_similarity) return {"", "no sufficiently similar enrolled person"};
    if (second > -1.5F && best - second < policy.minimum_margin) return {"", "ambiguous candidates"};
    return {best_id, "matched"};
}
}