cmake_minimum_required(VERSION 3.22)
project(czn_core LANGUAGES CXX)

# ---- generate mod_js.h from the JS bundle before compiling ------------------
find_package(Python3 COMPONENTS Interpreter REQUIRED)

set(CZN_JS_SRCS
    extract_js.py
    gen_headers.py
    06_spark_guard.js
    07_anim_skip.js)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/mod_js.h
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/extract_js.py
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/gen_headers.py
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    DEPENDS ${CZN_JS_SRCS}
    COMMENT "Assembling JS bundle -> mod_js.h"
    VERBATIM)

add_custom_target(czn_gen_js DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/mod_js.h)

# ---- the native injector ----------------------------------------------------
add_library(czn_core SHARED czn_core.cpp)

target_compile_options(czn_core PRIVATE
    -Os
    -std=c++17
    -Wall -Wextra -Wno-unused-parameter
    -fno-exceptions -fno-rtti -fno-stack-protector
    -mno-outline-atomics
    -ffunction-sections -fdata-sections)

# keep only the JNI export visible
target_compile_options(czn_core PRIVATE -fvisibility=hidden)

# the engine code avoids the C++ runtime entirely
target_link_options(czn_core PRIVATE
    -nostdlib++
    -Wl,--gc-sections
    -Wl,--as-needed)

target_link_libraries(czn_core log dl)

add_dependencies(czn_core czn_gen_js)
