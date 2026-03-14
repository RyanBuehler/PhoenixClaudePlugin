# C++ Cross-Platform Portability Reference

Practical guide for writing portable C++ targeting Linux and Windows.

> **Project rule:** No `#ifdef` platform guards in shared code. Platform-specific behavior belongs in dedicated liaison modules.

## Type Size Differences

### Data Model: LP64 (Linux) vs LLP64 (Windows)

| Type | Linux x64 | Windows x64 | Portable Alternative |
|------|-----------|-------------|---------------------|
| `short` | 2 bytes | 2 bytes | `int16_t` |
| `int` | 4 bytes | 4 bytes | `int32_t` |
| `long` | **8 bytes** | **4 bytes** | `int64_t` |
| `long long` | 8 bytes | 8 bytes | `int64_t` |
| `size_t` | 8 bytes | 8 bytes | `size_t` (for sizes) |
| `void*` | 8 bytes | 8 bytes | `uintptr_t` (for arithmetic) |
| `wchar_t` | **4 bytes** | **2 bytes** | `char8_t`, `char16_t`, `char32_t` |

**Rule:** Never use `long` for portable code. Use `int32_t` or `int64_t` from `<cstdint>`.

```cpp
// BAD: sizeof(long) differs
long timestamp = GetTimestamp();

// GOOD: explicit width
int64_t timestamp = GetTimestamp();
```

## char Signedness

`char` is signed on x86 but **unsigned** on ARM. This causes subtle bugs:

```cpp
// BAD: sign-dependent comparison
char c = buffer[i];
if (c < 0) { /* Works on x86, never true on ARM */ }

// GOOD: explicit signedness
uint8_t byte = buffer[i];
if (byte > 127) { /* Consistent everywhere */ }

// GOOD: for text processing
signed char c = buffer[i];  // Explicit sign
```

**Rule:** Use `uint8_t` for raw bytes, `signed char`/`unsigned char` when sign matters.

## Fixed-Width Types

```cpp
#include <cstdint>

// Exact-width integers
int8_t, uint8_t       // 1 byte
int16_t, uint16_t     // 2 bytes
int32_t, uint32_t     // 4 bytes
int64_t, uint64_t     // 8 bytes

// Size types
size_t                // Unsigned, for object sizes and array indexing
ptrdiff_t             // Signed, for pointer differences
uintptr_t             // Unsigned, for storing pointer values as integers
intptr_t              // Signed variant
```

### Format Specifiers for Fixed-Width Types

```cpp
#include <cinttypes>

int64_t val = 42;
printf("%" PRId64 "\n", val);   // Portable printf
printf("%" PRIx64 "\n", val);   // Hex

// Better: use std::format (C++20)
std::format("{}", val);  // Just works
```

## Filesystem API

### Path Separators

```cpp
// BAD: hardcoded separator
std::string path = dir + "/" + file;
std::string path = dir + "\\" + file;

// GOOD: std::filesystem handles separators
#include <filesystem>
auto path = std::filesystem::path(dir) / file;
```

### Common Portability Issues

| Issue | Linux | Windows | Portable Fix |
|-------|-------|---------|-------------|
| Path separator | `/` | `\` (also accepts `/`) | `std::filesystem::path` |
| Case sensitivity | Case-sensitive | Case-insensitive | Don't rely on case |
| Max path length | ~4096 | 260 (legacy), ~32K (long paths) | Keep paths short |
| Root paths | `/home/user/` | `C:\Users\user\` | `std::filesystem::temp_directory_path()` |
| Symlinks | Fully supported | Requires privileges | Check with `is_symlink()` |
| Permissions | POSIX (rwx) | ACLs | Use `std::filesystem::permissions()` |
| Hidden files | `.filename` | File attribute | Platform liaison |

### Safe Filesystem Operations

```cpp
namespace fs = std::filesystem;

// Check before operating
if (fs::exists(path) && fs::is_regular_file(path))
{
    auto size = fs::file_size(path);
    auto lastWrite = fs::last_write_time(path);
}

// Create directories
fs::create_directories(path / "sub" / "dir");

// Iterate directory
for (const auto& entry : fs::directory_iterator(dir))
{
    if (entry.is_regular_file() && entry.path().extension() == ".cpp")
    {
        Process(entry.path());
    }
}

// Portable temp directory
auto tmp = fs::temp_directory_path() / "phoenix-cache";
```

## Endianness

### Detection (C++20)

```cpp
#include <bit>

if constexpr (std::endian::native == std::endian::little)
{
    // x86, ARM (most modern systems)
}
else if constexpr (std::endian::native == std::endian::big)
{
    // PowerPC, some network equipment
}
```

### Byte Swapping (C++23)

```cpp
#include <bit>

uint32_t swapped = std::byteswap(value);  // C++23
```

### Network Byte Order

```cpp
// For network protocols, always convert to/from big-endian
uint32_t networkOrder = htonl(hostValue);
uint32_t hostOrder = ntohl(networkValue);
```

## Alignment

### Basics

```cpp
// Query alignment
alignof(int)      // Typically 4
alignof(double)   // Typically 8
alignof(void*)    // 4 or 8

// Specify alignment
struct alignas(16) AlignedData
{
    float x, y, z, w;
};

// Aligned allocation
auto* ptr = static_cast<float*>(std::aligned_alloc(16, sizeof(float) * 4));
```

### Struct Padding Differences

```cpp
struct Example
{
    char a;     // 1 byte
    // 3 bytes padding (on most platforms)
    int b;      // 4 bytes
    char c;     // 1 byte
    // 3 bytes padding
};
// sizeof = 12 on most platforms, but not guaranteed

// If you need exact layout (e.g., GPU buffers, file formats):
struct ExactLayout
{
    alignas(4) float x;
    alignas(4) float y;
    alignas(4) float z;
};
static_assert(sizeof(ExactLayout) == 12);
static_assert(offsetof(ExactLayout, y) == 4);
```

### Packed Structs (Avoid in Shared Code)

```cpp
// GCC/Clang only — don't use in shared code
struct __attribute__((packed)) Packed { ... };

// MSVC only
#pragma pack(push, 1)
struct Packed { ... };
#pragma pack(pop)

// Portable alternative: serialize field-by-field
void Serialize(const Header& h, std::span<uint8_t> buffer)
{
    memcpy(buffer.data(), &h.magic, 4);
    memcpy(buffer.data() + 4, &h.version, 2);
}
```

## Compiler Differences

### Attributes

| Feature | GCC/Clang | MSVC | Standard C++ |
|---------|-----------|------|-------------|
| Unused variable | `__attribute__((unused))` | `(void)var;` | `[[maybe_unused]]` |
| No return | `__attribute__((noreturn))` | `__declspec(noreturn)` | `[[noreturn]]` |
| Deprecated | `__attribute__((deprecated))` | `__declspec(deprecated)` | `[[deprecated]]` (forbidden in this project) |
| DLL export | `__attribute__((visibility("default")))` | `__declspec(dllexport)` | None standard |
| Force inline | `__attribute__((always_inline))` | `__forceinline` | None standard |
| Likely branch | `__builtin_expect(x, 1)` | N/A | `[[likely]]` (C++20) |

**Rule:** Use standard attributes (`[[maybe_unused]]`, `[[nodiscard]]`, `[[likely]]`) over compiler-specific ones.

### Warning Differences

| Warning | GCC/Clang | MSVC |
|---------|-----------|------|
| All warnings | `-Wall -Wextra` | `/W4` |
| Warnings as errors | `-Werror` | `/WX` |
| Specific warning off | `-Wno-unused-parameter` | `/wd4100` |
| Shadow variable | `-Wshadow` | `/W4` (includes) |
| Sign conversion | `-Wsign-conversion` | `/W4` (includes) |

### Predefined Macros

| Macro | GCC | Clang | MSVC |
|-------|-----|-------|------|
| Compiler ID | `__GNUC__` | `__clang__` | `_MSC_VER` |
| C++ version | `__cplusplus` | `__cplusplus` | `_MSVC_LANG` (use `/Zc:__cplusplus` to fix `__cplusplus`) |
| Platform | `__linux__` | `__linux__` / `__APPLE__` | `_WIN32` |
| Architecture | `__x86_64__` | `__x86_64__` | `_M_X64` |

**Project rule:** Don't use these in shared code. Platform detection belongs in CMake and liaison modules.

## Threading Portability

### std::thread vs Platform Threads

```cpp
// GOOD: Standard library (portable)
#include <thread>
#include <mutex>

std::thread worker([] { DoWork(); });
std::mutex mtx;
std::lock_guard lock(mtx);

// Platform-specific only in liaison modules:
// Linux: pthread_create, pthread_mutex
// Windows: CreateThread, CRITICAL_SECTION
```

### Cache Line Size

```cpp
// C++17 (not all implementations provide it)
#include <new>
constexpr size_t CacheLineSize = std::hardware_destructive_interference_size;

// Fallback: 64 bytes is correct for nearly all modern x86/ARM CPUs
constexpr size_t CacheLineSize = 64;
```

## String and Text

### UTF-8 Everywhere

```cpp
// Use std::string for UTF-8 text (the engine's internal encoding)
std::string name = "Phoenix Engine";

// Convert for Windows APIs in liaison modules:
// UTF-8 → UTF-16: MultiByteToWideChar(CP_UTF8, ...)
// UTF-16 → UTF-8: WideCharToMultiByte(CP_UTF8, ...)

// C++20 char8_t (opt-in, breaks string literal compatibility)
// Prefer std::string with UTF-8 content for now
```

### String Literals

```cpp
// These are portable
"Hello"              // char[] (UTF-8 on modern compilers)
u8"Hello"            // char8_t[] (C++20) or char[] (C++17)
u"Hello"             // char16_t[] (UTF-16)
U"Hello"             // char32_t[] (UTF-32)
L"Hello"             // wchar_t[] (DO NOT use in shared code — size varies)
```

## Standard Library Divergences

### Implementation-Defined Behavior

| Behavior | Varies? | Portable Approach |
|----------|---------|-------------------|
| `unordered_map` iteration order | Yes | Don't depend on order |
| `std::string` SSO buffer size | Yes (~15–22 chars) | Don't assume specific size |
| `std::regex` performance | Dramatically | Avoid in hot paths |
| `sizeof(std::mutex)` | Yes (40 on Linux, 80 on Windows) | Don't embed in tight structs |
| `std::filesystem::path::preferred_separator` | `/` vs `\` | Use `/` operator |

### Locale Differences

```cpp
// BAD: Locale-dependent (may use comma for decimal)
double d = std::stod("3.14");

// GOOD: Locale-independent parsing
std::from_chars(str.data(), str.data() + str.size(), d);
```

## Common Traps

### __FILE__ Path Format

```cpp
// GCC/Clang: /home/user/project/src/file.cpp
// MSVC: C:\Users\user\project\src\file.cpp
// Some: relative path from build dir

// Portable: use std::source_location (C++20)
#include <source_location>
void Log(std::source_location loc = std::source_location::current())
{
    std::println("{}:{}", loc.file_name(), loc.line());
}
```

### #pragma once

Widely supported but technically non-standard. This project requires it — never use traditional include guards.

### offsetof Limitations

```cpp
// Works reliably only on standard-layout types
#include <cstddef>
static_assert(std::is_standard_layout_v<MyStruct>);
size_t off = offsetof(MyStruct, member);
```

### Bit Fields

```cpp
// Layout is implementation-defined — avoid in portable structs
struct Flags
{
    uint32_t active : 1;   // Bit position varies by compiler
    uint32_t type : 3;
};

// Portable alternative: manual bit manipulation
constexpr uint32_t FLAG_ACTIVE = 1 << 0;
constexpr uint32_t FLAG_TYPE_MASK = 0b1110;
```
