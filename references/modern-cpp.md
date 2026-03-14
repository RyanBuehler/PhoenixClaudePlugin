# Modern C++ Quick Reference (C++20/23/26)

Practical reference for Phoenix Engine development. Features marked with exceptions warnings where applicable.

> **Project rule:** `try`, `catch`, `throw`, and `noexcept` are **forbidden**. Use `std::expected`, `std::optional`, or error codes instead.

## C++20 Features

### Concepts and Constraints

Replace SFINAE and `static_assert` with readable compile-time requirements.

```cpp
// Define a concept
template<typename T>
concept Numeric = std::integral<T> || std::floating_point<T>;

// Use in template
template<Numeric T>
T Clamp(T value, T min, T max)
{
    return std::max(min, std::min(value, max));
}

// Inline constraint
template<typename T>
    requires std::derived_from<T, IModule>
void RegisterModule(T& module);

// Abbreviated function templates
void Process(std::integral auto value);
```

**Replaces:** `std::enable_if`, SFINAE tricks, `static_assert` on types.

### Ranges and Views

Composable, lazy sequence operations.

```cpp
#include <ranges>

// Filter and transform
auto results = modules
    | std::views::filter([](const auto& m) { return m.IsActive(); })
    | std::views::transform([](const auto& m) { return m.GetName(); });

// Take first N
auto topFive = scores | std::views::take(5);

// Enumerate (C++23 technically, but widely available)
for (auto [i, val] : items | std::views::enumerate)
{
    LOG_DEBUG("Item {}: {}", i, val);
}
```

**Replaces:** manual loops with index tracking, iterator pairs with `std::transform`.

### std::format

Type-safe formatting without `printf` pitfalls.

```cpp
#include <format>

std::string msg = std::format("Module '{}' initialized in {:.2f}ms", name, elapsed);
std::string hex = std::format("{:#x}", address);
std::string padded = std::format("{:>20}", text);  // Right-align, width 20
```

**Replaces:** `sprintf`, `snprintf`, `std::stringstream` assembly.

### std::span

Non-owning view over contiguous memory.

```cpp
#include <span>

void ProcessData(std::span<const float> data)
{
    for (float val : data) { /* ... */ }
}

// Works with vectors, arrays, C arrays
std::vector<float> vec = {1.0f, 2.0f, 3.0f};
ProcessData(vec);

float arr[] = {1.0f, 2.0f};
ProcessData(arr);
```

**Replaces:** `(const float* data, size_t size)` pointer+size pairs.

### Three-Way Comparison (Spaceship Operator)

```cpp
struct Version
{
    int Major;
    int Minor;
    int Patch;

    auto operator<=>(const Version&) const = default;
};

// Automatically generates <, <=, >, >=, ==, !=
Version a{1, 2, 0};
Version b{1, 3, 0};
bool older = (a < b);  // true
```

**Replaces:** manually writing 6 comparison operators.

### consteval and constinit

```cpp
// consteval: MUST be evaluated at compile time (replaces some macros)
consteval int ComputeHash(const char* str)
{
    int hash = 0;
    while (*str) hash = hash * 31 + *str++;
    return hash;
}

// constinit: initialized at compile time but mutable at runtime
constinit int g_StartupValue = ComputeHash("Phoenix");
```

### Designated Initializers

```cpp
struct WindowConfig
{
    uint32_t Width = 1280;
    uint32_t Height = 720;
    bool Fullscreen = false;
    bool VSync = true;
};

auto config = WindowConfig{
    .Width = 1920,
    .Height = 1080,
    .Fullscreen = true,
    // .VSync uses default
};
```

### std::jthread (Self-Joining Thread)

```cpp
#include <thread>

{
    std::jthread worker([](std::stop_token stopToken) {
        while (!stopToken.stop_requested())
        {
            DoWork();
        }
    });
    // Automatically joins on scope exit
    // Can request stop: worker.request_stop();
}
```

**Replaces:** `std::thread` + manual `join()` + manual stop flags.

### [[likely]] and [[unlikely]]

```cpp
if (errorCode != 0) [[unlikely]]
{
    HandleError(errorCode);
}
else [[likely]]
{
    ProcessResult();
}
```

### Calendar and Time Zones (chrono)

```cpp
#include <chrono>

using namespace std::chrono;
auto now = system_clock::now();
auto today = floor<days>(now);
year_month_day ymd{today};

// Duration literals
auto timeout = 500ms;
auto frame = 16667us;  // ~60 FPS
```

## C++23 Features

### std::expected

Error handling without exceptions — the project's preferred pattern.

```cpp
#include <expected>

enum class FileError { NotFound, PermissionDenied, IOError };

std::expected<std::string, FileError> ReadFile(const char* path)
{
    if (!Exists(path))
        return std::unexpected(FileError::NotFound);

    return std::string{/* file contents */};
}

// Usage
auto result = ReadFile("config.json");
if (result)
{
    Process(result.value());
}
else
{
    HandleError(result.error());
}

// Monadic operations
auto parsed = ReadFile("config.json")
    .transform([](const std::string& s) { return Parse(s); })
    .transform_error([](FileError e) { return ToString(e); });
```

**Replaces:** error codes with out-parameters, `std::optional` without error info.

### std::print / std::println

```cpp
#include <print>

std::println("Hello, {}!", name);         // With newline
std::print("Progress: {:.1f}%", pct);     // Without newline
std::println(stderr, "Error: {}", msg);   // To specific stream
```

**Replaces:** `std::cout << "Hello, " << name << "!" << std::endl;`

### Deducing this

```cpp
class Widget
{
public:
    // Single implementation for const and non-const
    template<typename Self>
    auto&& GetName(this Self&& self)
    {
        return std::forward<Self>(self).m_Name;
    }

    // CRTP without templates
    void DoSomething(this auto& self)
    {
        self.Implementation();  // Calls derived class method
    }

private:
    std::string m_Name;
};
```

**Replaces:** duplicated const/non-const method overloads, traditional CRTP.

### std::flat_map / std::flat_set

Cache-friendly sorted containers backed by contiguous storage.

```cpp
#include <flat_map>

std::flat_map<std::string, int> scores;
scores["Alice"] = 100;
scores["Bob"] = 95;

// Better cache performance than std::map for small-to-medium sizes
// Sorted, so iteration is ordered
```

**Replaces:** `std::map` when cache performance matters more than insertion speed.

### Ranges Improvements (zip, chunk, slide, etc.)

```cpp
#include <ranges>

// Zip two ranges together
std::vector<std::string> names = {"Alice", "Bob"};
std::vector<int> scores = {100, 95};

for (auto [name, score] : std::views::zip(names, scores))
{
    std::println("{}: {}", name, score);
}

// Chunk into groups
for (auto chunk : data | std::views::chunk(4))
{
    ProcessBatch(chunk);
}

// Sliding window
for (auto window : data | std::views::slide(3))
{
    ProcessWindow(window);
}

// Cartesian product
for (auto [x, y] : std::views::cartesian_product(xs, ys))
{
    Process(x, y);
}
```

### if consteval

```cpp
constexpr int Compute(int x)
{
    if consteval
    {
        // Compile-time path (can use consteval functions)
        return SlowButPrecise(x);
    }
    else
    {
        // Runtime path (can use SIMD, etc.)
        return FastApproximate(x);
    }
}
```

### std::mdspan (Multi-Dimensional Span)

```cpp
#include <mdspan>

void ProcessMatrix(std::mdspan<float, std::dextents<size_t, 2>> matrix)
{
    for (size_t i = 0; i < matrix.extent(0); ++i)
        for (size_t j = 0; j < matrix.extent(1); ++j)
            matrix[i, j] *= 2.0f;
}

// Wrap existing data
std::vector<float> data(100);
auto mat = std::mdspan(data.data(), 10, 10);
ProcessMatrix(mat);
```

### std::stacktrace

```cpp
#include <stacktrace>

void LogCrash()
{
    auto trace = std::stacktrace::current();
    for (const auto& frame : trace)
    {
        std::println("  {} ({}:{})",
            frame.description(), frame.source_file(), frame.source_line());
    }
}
```

## C++26 Preview

Features with strong consensus, expected in C++26:

### Contracts (P2900)

```cpp
int Sqrt(int x)
    pre(x >= 0)          // Precondition
    post(r: r >= 0)      // Postcondition
{
    return static_cast<int>(std::sqrt(x));
}
```

**Status:** Accepted for C++26. Replaces manual `assert()` with language-level support.

### Reflection (P2996)

```cpp
// Compile-time introspection of types
template<typename T>
void PrintMembers(const T& obj)
{
    template for (constexpr auto member : std::meta::members_of(^T))
    {
        std::println("{}: {}", std::meta::name_of(member), obj.[:member:]);
    }
}
```

**Status:** Strong consensus, targeting C++26.

### Pattern Matching (P2688)

```cpp
inspect(value)
{
    0 => std::println("zero");
    1 => std::println("one");
    int n if n > 0 => std::println("positive: {}", n);
    _ => std::println("other");
};
```

**Status:** Under active development, targeting C++26.

### std::execution (Senders/Receivers)

Structured async framework for heterogeneous execution:

```cpp
auto work = std::execution::schedule(threadPool)
    | std::execution::then([] { return ComputeData(); })
    | std::execution::then([](auto data) { return Process(data); });

std::execution::sync_wait(work);
```

**Status:** Accepted for C++26.

## Common Migration Patterns

| Old Pattern | Modern Alternative | Standard |
|-------------|-------------------|----------|
| `typedef` | `using` | C++11 |
| `NULL` | `nullptr` | C++11 |
| `(int)x` C-cast | `static_cast<int>(x)` | C++11 |
| `#define CONST 42` | `constexpr int CONST = 42` | C++11 |
| `std::bind` | Lambda expressions | C++11 |
| SFINAE `enable_if` | Concepts `requires` | C++20 |
| `sprintf` | `std::format` | C++20 |
| `ptr + size` pair | `std::span` | C++20 |
| 6 comparison operators | `operator<=>` = default | C++20 |
| Error codes + out-params | `std::expected` | C++23 |
| `std::cout <<` chaining | `std::println` | C++23 |
| `std::map` (small sets) | `std::flat_map` | C++23 |
| Manual assert() | Contracts `pre`/`post` | C++26 |

## Exception-Related Features — Project Alternatives

These C++ features involve exceptions. The project forbids them, so use the listed alternatives.

| Feature | Project Alternative |
|---------|-------------------|
| `throw` / `catch` | `std::expected`, error codes, `std::optional` |
| `noexcept` specifier | Omit entirely (all code is implicitly no-throw) |
| `std::current_exception` | Not applicable |
| `std::exception_ptr` | Not applicable |
| `std::nested_exception` | Not applicable |
| `ExceptionGroup` (Python) | Not applicable to C++ |
