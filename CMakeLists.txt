cmake_minimum_required(VERSION 3.20)
project(KONJE VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenSSL REQUIRED)
find_package(SQLite3 REQUIRED)
find_package(Threads REQUIRED)

add_library(konje_core STATIC
    src/profile_store.cpp
    src/policy.cpp
    src/scheduler.cpp
    src/process.cpp
    src/pipeline.cpp
)
target_include_directories(konje_core PUBLIC include)
target_link_libraries(konje_core PUBLIC OpenSSL::Crypto SQLite::SQLite3 Threads::Threads)
target_compile_options(konje_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion)

add_executable(konje src/main.cpp)
target_link_libraries(konje PRIVATE konje_core)
target_compile_options(konje PRIVATE -Wall -Wextra -Wpedantic)

include(CTest)
if(BUILD_TESTING)
    add_executable(konje_tests tests/tests.cpp)
    target_link_libraries(konje_tests PRIVATE konje_core)
    add_test(NAME konje_core_tests COMMAND konje_tests)
    add_test(NAME konje_help COMMAND konje --help)
    find_program(KONJE_PYTHON3 NAMES python3 REQUIRED)
    if(KONJE_PYTHON3)
        add_test(NAME burst_worker_protocol
                 COMMAND ${KONJE_PYTHON3} ${CMAKE_SOURCE_DIR}/tools/test_worker_protocol.py)
        add_test(NAME mock_full_pipeline
                 COMMAND ${KONJE_PYTHON3} ${CMAKE_SOURCE_DIR}/tests/mock_pipeline.py $<TARGET_FILE:konje>)
    endif()
endif()