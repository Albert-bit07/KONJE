#pragma once
#include "konje/model.hpp"

namespace konje {
MatchResult decide_match(const std::vector<float>& candidate,
                         const std::vector<Profile>& enrolled,
                         MatchPolicy policy);
}