# Modern CMake Quick Reference (3.20+)

Practical reference for target-based CMake builds in a cross-platform C++ engine.

## Target-Based Builds

### The Golden Rule

Never use directory-level commands. Always use target-level commands.

```cmake
# BAD (directory-level, leaks to everything in directory)
include_directories(${SOME_DIR})
link_libraries(somelib)
add_definitions(-DFOO)

# GOOD (target-level, explicit scope)
target_include_directories(MyTarget PRIVATE ${SOME_DIR})
target_link_libraries(MyTarget PRIVATE somelib)
target_compile_definitions(MyTarget PRIVATE FOO)
```

### Visibility Keywords

| Keyword | Meaning | Use Case |
|---------|---------|----------|
| `PRIVATE` | Only for this target | Implementation details |
| `PUBLIC` | This target AND consumers | Public API headers/libs |
| `INTERFACE` | Only for consumers | Header-only libraries |

```cmake
target_link_libraries(Engine
    PUBLIC   Core             # Engine's public API uses Core types
    PRIVATE  InternalHelper   # Only used internally
)
```

### File Sets (CMake 3.23+)

Modern header management that's install-aware.

```cmake
add_library(MyModule)

target_sources(MyModule
    PRIVATE
        Source/Implementation.cpp
    PUBLIC
        FILE_SET HEADERS
        BASE_DIRS Include
        FILES
            Include/MyModule/Public.h
            Include/MyModule/Types.h
)

# Install respects file sets automatically
install(TARGETS MyModule FILE_SET HEADERS)
```

**Replaces:** manual `target_include_directories` + `install(FILES ...)` pairs.

## Generator Expressions

Evaluated at generate time, not configure time. Cannot be printed with `message()`.

### Common Generator Expressions

```cmake
# Configuration
$<CONFIG>                           # Current config name
$<CONFIG:Release>                   # True if Release
$<$<CONFIG:Debug>:_debug>           # "_debug" suffix in Debug only

# Target properties
$<TARGET_FILE:tgt>                  # Full path to output file
$<TARGET_FILE_DIR:tgt>              # Directory of output file
$<TARGET_FILE_NAME:tgt>             # Filename only
$<TARGET_RUNTIME_DLLS:tgt>          # DLLs needed at runtime (Windows)
$<TARGET_PROPERTY:tgt,prop>         # Read target property

# Build vs install
$<BUILD_INTERFACE:path>             # Only in build tree
$<INSTALL_INTERFACE:path>           # Only after install

# Platform
$<PLATFORM_ID:Linux>               # True on Linux
$<$<PLATFORM_ID:Windows>:ws2_32>   # Link ws2_32 on Windows only

# Compiler
$<CXX_COMPILER_ID:GNU>             # True for GCC
$<$<CXX_COMPILER_ID:MSVC>:/W4>     # /W4 for MSVC only

# Conditionals
$<$<BOOL:${TESTS}>:test_lib>       # Link test_lib if TESTS is true
$<IF:$<CONFIG:Debug>,debug,release> # Ternary
```

### Debugging Generator Expressions

```cmake
# Use file(GENERATE) to inspect values
file(GENERATE
    OUTPUT "${CMAKE_BINARY_DIR}/genex-debug-$<CONFIG>.txt"
    CONTENT "File: $<TARGET_FILE:MyTarget>\nConfig: $<CONFIG>\n"
)

# Or echo at build time
add_custom_command(TARGET MyTarget POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E echo "Built: $<TARGET_FILE:MyTarget>"
)
```

## CMake Presets

### CMakePresets.json

```json
{
  "version": 6,
  "configurePresets": [
    {
      "name": "linux-release",
      "displayName": "Linux Release",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build-release",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Release",
        "TESTS": "ON"
      },
      "condition": {
        "type": "equals",
        "lhs": "${hostSystemName}",
        "rhs": "Linux"
      }
    },
    {
      "name": "linux-debug",
      "inherits": "linux-release",
      "displayName": "Linux Debug",
      "binaryDir": "${sourceDir}/build-debug",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Debug"
      }
    }
  ],
  "buildPresets": [
    {
      "name": "linux-release",
      "configurePreset": "linux-release",
      "jobs": 0
    }
  ],
  "testPresets": [
    {
      "name": "linux-release",
      "configurePreset": "linux-release",
      "output": { "outputOnFailure": true }
    }
  ]
}
```

### Using Presets

```bash
cmake --preset linux-release
cmake --build --preset linux-release
ctest --preset linux-release
```

## FetchContent

### Basic Usage

```cmake
include(FetchContent)

FetchContent_Declare(
    fmt
    GIT_REPOSITORY https://github.com/fmtlib/fmt.git
    GIT_TAG 10.2.0
    GIT_SHALLOW TRUE
)

FetchContent_MakeAvailable(fmt)
target_link_libraries(MyTarget PRIVATE fmt::fmt)
```

### Options Before MakeAvailable

```cmake
# Disable parts of dependency before making available
set(FMT_DOC OFF CACHE BOOL "" FORCE)
set(FMT_TEST OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(fmt)
```

### Offline Builds

```bash
# Populate once, then disconnect
cmake -DFETCHCONTENT_FULLY_DISCONNECTED=ON ...
```

### find_package Fallback Pattern

```cmake
find_package(fmt QUIET)
if(NOT fmt_FOUND)
    FetchContent_Declare(fmt
        GIT_REPOSITORY https://github.com/fmtlib/fmt.git
        GIT_TAG 10.2.0
    )
    FetchContent_MakeAvailable(fmt)
endif()
target_link_libraries(MyTarget PRIVATE fmt::fmt)
```

## find_package

### Config Mode vs Module Mode

```cmake
# Config mode (preferred) — looks for FooConfig.cmake
find_package(Foo CONFIG REQUIRED)

# Module mode — looks for FindFoo.cmake in CMAKE_MODULE_PATH
find_package(Foo MODULE REQUIRED)

# Default: tries config first, then module
find_package(Foo REQUIRED)
```

### Version Requirements

```cmake
find_package(Vulkan 1.3 REQUIRED)           # Minimum version
find_package(OpenSSL 1.1...3.0 REQUIRED)    # Version range (3.19+)
```

### Creating a Config Package

```cmake
include(CMakePackageConfigHelpers)

install(TARGETS MyLib EXPORT MyLibTargets)

install(EXPORT MyLibTargets
    FILE MyLibTargets.cmake
    NAMESPACE MyLib::
    DESTINATION lib/cmake/MyLib
)

write_basic_package_version_file(
    MyLibConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    MyLibConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/MyLibConfigVersion.cmake
    DESTINATION lib/cmake/MyLib
)
```

## Modern Variable Patterns

### option() and cmake_dependent_option

```cmake
option(TESTS "Enable building tests" OFF)
option(BUILD_SHARED_LIBS "Build shared libraries" ON)

include(CMakeDependentOption)
cmake_dependent_option(
    BUILD_EDITOR "Build the editor"
    ON                    # Default when condition is met
    "NOT HEADLESS_BUILD"  # Condition
    OFF                   # Default when condition not met
)
```

### List Operations

```cmake
set(SOURCES main.cpp utils.cpp)
list(APPEND SOURCES extra.cpp)
list(REMOVE_ITEM SOURCES utils.cpp)
list(LENGTH SOURCES count)
list(FILTER SOURCES INCLUDE REGEX ".*\\.cpp$")
list(SORT SOURCES)
list(TRANSFORM SOURCES PREPEND "${CMAKE_CURRENT_SOURCE_DIR}/")
```

### Cache Variables

```cmake
# Set cache variable (user-configurable)
set(APPLICATION "Editor" CACHE STRING "Application to build")
set_property(CACHE APPLICATION PROPERTY STRINGS "Editor;Game;Minimal")

# Force override (use sparingly)
set(SOME_VAR "value" CACHE STRING "" FORCE)
```

## Unity Builds

```cmake
# Enable globally
set(CMAKE_UNITY_BUILD ON)
set(CMAKE_UNITY_BUILD_BATCH_SIZE 16)

# Or per-target
set_target_properties(MyTarget PROPERTIES
    UNITY_BUILD ON
    UNITY_BUILD_BATCH_SIZE 8
)

# Exclude specific files from unity build
set_source_files_properties(SpecialFile.cpp PROPERTIES
    SKIP_UNITY_BUILD_INCLUSION ON
)
```

**Important:** Anonymous namespaces break unity builds (ODR violations when files merge). Always use named namespaces.

## Precompiled Headers

```cmake
# Basic usage
target_precompile_headers(MyTarget PRIVATE
    <vector>
    <string>
    <memory>
    <unordered_map>
    "MyPCH.h"
)

# Reuse from another target (share PCH)
target_precompile_headers(OtherTarget REUSE_FROM MyTarget)

# Exclude specific files
set_source_files_properties(NoPCH.cpp PROPERTIES
    SKIP_PRECOMPILE_HEADERS ON
)
```

## Common Anti-Patterns

### Don't: Use Directory-Level Commands

```cmake
# BAD
include_directories(${FOO_INCLUDE})
link_directories(${FOO_LIB})
add_definitions(-DFOO_ENABLED)

# GOOD
target_include_directories(MyTarget PRIVATE ${FOO_INCLUDE})
target_link_libraries(MyTarget PRIVATE Foo::Foo)
target_compile_definitions(MyTarget PRIVATE FOO_ENABLED)
```

### Don't: Use file(GLOB) for Sources

```cmake
# BAD — new files not detected until re-configure
file(GLOB SOURCES "src/*.cpp")

# GOOD — explicit source list, always correct
target_sources(MyTarget PRIVATE
    src/main.cpp
    src/engine.cpp
    src/renderer.cpp
)
```

### Don't: Set Global Compiler Flags

```cmake
# BAD — affects everything
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall")

# GOOD — scoped to target
target_compile_options(MyTarget PRIVATE -Wall)
```

### Don't: Hardcode Paths

```cmake
# BAD
set(INCLUDE_DIR "/usr/local/include")

# GOOD
find_package(Foo REQUIRED)
target_link_libraries(MyTarget PRIVATE Foo::Foo)
```

### Don't: Use CMAKE_SOURCE_DIR

```cmake
# BAD — breaks when used as subdirectory
${CMAKE_SOURCE_DIR}/include

# GOOD — relative to current CMakeLists.txt
${CMAKE_CURRENT_SOURCE_DIR}/include

# GOOD — relative to project root
${PROJECT_SOURCE_DIR}/include
```

## Useful Commands Reference

| Command | Purpose |
|---------|---------|
| `cmake -S . -B build` | Configure out-of-source |
| `cmake --build build -j$(nproc)` | Build with parallelism |
| `cmake --build build --target MyTarget` | Build single target |
| `cmake -L build` | List cache variables |
| `cmake --install build --prefix /usr/local` | Install |
| `cmake -S . -B build --trace-expand` | Verbose configure |
| `cmake --build build --clean-first` | Clean before build |
| `cmake --preset <name>` | Use a preset |
