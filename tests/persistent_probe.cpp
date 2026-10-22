#include "konje/persistent_client.hpp"
#include <chrono>
#include <iostream>
#include <string>
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const std::string jpeg = "\xff\xd8TEST\xff\xd9";
    std::string burst = "KONJE1";
    burst.push_back('\1');
    for (int n = 0; n < 4; ++n) burst.push_back(static_cast<char>((jpeg.size() >> (n * 8)) & 255));
    burst += jpeg;
    auto result = konje::persistent_infer(argv[1], argv[2], burst, [] { return true; },
                                           std::chrono::seconds(3));
    if (!result) { std::cout << "UNAVAILABLE\n"; return 0; }
    std::cout << *result;
    return 0;
}