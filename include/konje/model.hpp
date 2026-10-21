#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace konje {
struct Profile {
    std::string id;              // An opaque, non-identifying local ID.
    std::string name;
    std::string relationship;
    std::string introduction;    // Explicitly approved speech, never generated.
    std::vector<float> embedding;
};

struct MatchPolicy {
    float minimum_similarity{0.60F}; // Experimental only; must be evaluated.
    float minimum_margin{0.10F};     // Gap to second-best candidate.
};

struct MatchResult {
    std::string id; // Empty means uncertain.
    std::string reason;
};
}