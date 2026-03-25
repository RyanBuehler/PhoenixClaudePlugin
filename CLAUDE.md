# Phoenix Engine — Architecture Notes

## Hard Requirements

- **NEVER mention Claude Code in commit messages.** No "Generated with Claude Code", no Co-Authored-By Claude, nothing. Commit messages should look like they were written by a human developer.
- **Never combine `cd` and `git` in a compound command** (e.g. `cd /some/dir && git status`). Changing into an untrusted directory before running git exposes you to bare repository attacks where a malicious `.git` config can execute arbitrary code. Always run git commands using absolute paths or from the known working directory.

## Modules vs Subsystems

These are distinct concepts. Do NOT conflate them.

- **Modules** are self-contained components that register with `ModuleRegistry` via `IModule`.
  Engine manages module lifecycle (create, initialize, tick, shutdown) through `ModuleRegistry`/`IModuleBase`.
  Modules live as peers under `Modules/{Domain}/` — no nested submodules.

- **Subsystems** are abstract service interfaces (`ISubsystem`) for cross-module communication.
  Modules access each other's services through subsystem interfaces (e.g., `ITerminalService`, `IInputService`).
  A module registers its subsystem during `RegisterSubsystem()` and unregisters during `UnregisterSubsystem()`.

Engine interacts with modules ONLY through `ModuleRegistry` and `IModuleBase`. It accesses module
services through non-template subsystem interfaces (`ITerminalService`, `IInputService`), not
concrete module types.

## Engine Independence

Engine depends only on Core. All module dependencies are opt-in via Application description JSON
(`requires_module` in `*Description.json`). The `Minimal` application builds Engine with zero
module dependencies for CI validation.

## Module Structure

All modules are peers under `Modules/{Domain}/`:
- `Modules/Core/` — Engine, Arbiter, Archive, Soulforge, Terminal
- `Modules/Rendering/` — Aurora, Prism, Glyph, Montage, VulkanBackend, HeadlessBackend, HeadlessPane
- `Modules/Input/` — Impulse, Signal, Conduit, UserConduit, SyntheticConduit, XInput
- `Modules/Platform/` — PlatformLiaison, LinuxLiaison, LinuxAudio, LinuxInput, LinuxPane, LinuxFileManager, WindowsLiaison, WindowsAudio, WindowsInput, WindowsPane, WindowsFileManager, HeadlessLiaison
- `Modules/Audio/` — Sonic

## No Preprocessor Guards for Modularity

The project does not use `#ifdef` for feature/module gating. Modularity is driven by:
- JSON metadata (`*Description.json`) declaring module dependencies
- CMake (`SetupModule.cmake`) resolving and building only required modules
- Runtime checks via `Subsystem::Get<>()` for optional service availability

## Build System

- Applications declare their module needs in `*Description.json` `requires_module` arrays
- `SetupModule.cmake` recursively resolves dependencies from domain directories
- Missing dependencies cause graceful skip, not fatal errors
- `APPLICATION` cache variable selects which app to build: `Editor`, `Game`, or `Minimal`

## CI

The Linux CI workflow (`.github/workflows/ci.yml`) runs three sequential jobs on PR:

1. **Linux: Modularity** — Validates Engine builds with only Core (Minimal application)
2. **Linux: Build & Test (Incremental)** — Full build with ccache, runs BASE_TRIAL tests
3. **Linux: Format & Lint** — Checks formatting and runs clang-tidy

Jobs run in order; failure in any job skips subsequent jobs.

## Code Guidelines

For all code style and design practices, follow `Docs/StyleGuide.md`.

- Only make cosmetic changes to code you explicitly modify or add.
- Never reformat code unless you're already modifying it. When reformatting, follow
  `Docs/StyleGuide.md` for style.
- Follow the style of surrounding code.
- Always give namespaces explicit names; anonymous namespaces break our unity builds.
- Never introduce namespaces whose names contain the word "Detail".
- Do not use C++ exceptions. The keywords `try`, `catch`, `throw`, and `noexcept` are forbidden.
- RTTI is disabled. Do not use `dynamic_cast`, `typeid`, or `reinterpret_cast`.
- Do not use deprecated attributes or mark code as deprecated. The `[[deprecated]]` attribute is forbidden.
- Keep platform-specific logic (for example, Linux-only behavior) confined to
  the corresponding platform liaison sources so code for other platforms remains
  encapsulated and unaffected.
- Apply const correctness by default: const local variables, const reference parameters, const member functions for accessors.
- For every use of `std::memory_order`, add a nearby comment explaining why that ordering is required.
- After changing C/C++ code, run `python Tools/format.py --files=staged`
  to apply `clang-format`, then `python Tools/format.py --files=staged -error`
  to verify formatting. Run `python Tools/tidy.py` to check for clang-tidy
  warnings. If the script reports a missing compilation database, regenerate
  it once per build directory with `python Tools/tidy.py --compdb` (optionally
  keeping your `--filter` arguments); this leaves `build/compile_commands.json`
  in place for subsequent tidy runs. Test sources matching `*Trials.cpp` may
  be skipped by passing `--filter *Trials.cpp`.

## Color Values

- All floating-point color types (`Color::Red`, `Colors::RGBA`, `Colors::RGB`, etc.) use
  the **0.0–1.0** normalized range, NOT 0.0–255.0. A pure red is `Color::Red` = `{1.0f, 0.0f, 0.0f, 1.0f}`,
  not `{255.0f, 0.0f, 0.0f, 255.0f}`.
- When constructing colors from 8-bit inputs (e.g., hex codes, UI pickers), divide each
  channel by 255.0f before storing.

## Code Style

### C++
- Use traditional return type syntax (`T Foo()`), not trailing return types (`auto Foo() -> T`).
- When a variable is declared only to be immediately null/validity-checked, prefer combining
  the declaration and check into a single `if`-init-statement:
  ```cpp
  // Prefer:
  if (auto* Subscriber = Registry.Find(id); !Subscriber)
  {
      return;
  }

  // Instead of:
  auto* Subscriber = Registry.Find(id);
  if (!Subscriber) { return; }
  ```
  If the initializer expression is long or complex enough that the combined line becomes hard
  to read, break it into a separate declaration and `if` instead. Readability wins over brevity.

### Python
- Use single tabs for indentation.

### CMake
- Use single tabs for indentation.

### YAML
- Use two spaces for indentation.

## Build & Test Verification

- Do NOT run builds or tests after every code change. Only run the full
  verification sequence **immediately before committing** (i.e., when the user
  asks to commit or you are about to create a commit). This overrides any
  TDD or verification-before-completion guidance from other skills.
- To verify compilation and run all tests locally, mirror the CI pipeline.
- It is mandatory to configure the build with tests enabled and execute the
  full suite before committing:
        cmake -S . -B build -DTESTS=ON -DCMAKE_BUILD_TYPE=Release
        cmake --build build --config Release --parallel
        python Tools/format.py --files=staged
        python Tools/format.py --files=staged -error
        ctest --test-dir build -C Release --output-on-failure
- When presenting solutions, always ensure the project builds cleanly in Release
  and Headless configurations, and run all appropriate tests beforehand.

## Screenshot Capabilities

### Commands

- `aurora.screenshot` - Capture screenshot(s) from a running engine. Parameters: `frames` (default 1), `countdown` (seconds delay, default 0).
- `aurora.screenshot.exit` - Capture a single screenshot (with 2-second stabilization delay) then shut down the engine. Used for one-shot capture workflows.

### Output

- Screenshots are saved to `Screenshots/` as `capture-YYYYMMDD-HHMMSS-NNN.png`
- After each successful capture, the full path is written to `Screenshots/.last-capture`
- Read `.last-capture` to discover the most recent screenshot without timestamp guessing

### Console Pipe

Launch the engine with `--console-pipe=PATH` to enable external command injection via a FIFO:

```bash
# Launch with pipe
./cmake-build-release/bin/Phoenix --console-pipe=/tmp/phoenix-console.fifo

# Send commands from another process
echo "aurora.screenshot" > /tmp/phoenix-console.fifo
```

The pipe accepts one command per line. Commands are queued and executed on the main thread each tick.

## Subagent Definitions

The following agents are available for specialized tasks. Each is defined in `agents/`.

### Core Development
- `invoke-code-reviewer` — C++ code review for bugs, UB, style, portability, and modern C++23 improvements
- `invoke-lint-agent` — Runs clang-tidy for static analysis and bug detection
- `invoke-include-analyzer` — IWYU analysis, circular include detection, PCH optimization

### Architecture & Design
- `invoke-systems-designer` — Cross-platform module architecture and interface design
- `invoke-rendering-designer` — Render graph, material system, and GPU resource architecture
- `invoke-build-engineer` — CMake, CI/CD, cross-platform builds, and toolchain configuration

### Graphics & Rendering
- `invoke-vulkan-agent` — Vulkan API implementation, synchronization, descriptors, and pipelines
- `invoke-shader-expert` — GLSL/SPIR-V compilation, debugging, validation, and optimization

### Platform
- `invoke-linux-agent` — Linux platform C++ development, POSIX APIs, and liaison modules
- `invoke-windows-agent` — Windows platform C++ development, Win32 APIs, and liaison modules

### Testing & Debugging
- `invoke-test-engineer` — Test setup, strategy, coverage, debugging failing tests
- `invoke-debugger-agent` — GDB/LLDB workflows, breakpoints, core dump analysis
- `invoke-memory-agent` — Memory leak detection, ASan/MSan/LSan, Valgrind

### Performance
- `invoke-perf-agent` — CPU profiling, cache analysis, benchmarking, optimization
- `invoke-concurrency-agent` — Thread safety, lock-free algorithms, synchronization

### Capture & Analysis
- `invoke-screenshot-agent` — Screenshot capture and visual analysis of the running engine

### Display Requirements

Screenshots require a display server (X11 or Wayland). On headless CI, use `xvfb-run`:

```bash
xvfb-run ./cmake-build-release/bin/Phoenix --aurora.screenshot.exit
```

## Reference Documents

The `references/` directory contains quick-reference guides that agents can consult:

- `modern-cpp.md` — C++20/23/26 features, idioms, and migration patterns
- `modern-cmake.md` — Target-based builds, presets, FetchContent, generator expressions
- `modern-python.md` — Python 3.12+ features, pathlib, type hints, CLI patterns
- `modern-vulkan.md` — Dynamic rendering, descriptor buffers, synchronization2, timeline semaphores
- `cpp-portability.md` — Cross-platform pitfalls, fixed-width types, alignment, char signedness
- `code-style.md` — Formatting stack, clang-format/clang-tidy configuration, tool architecture

## Permissions

Add new tool permissions to the **user-level** settings (`~/.claude/settings.json`), not the
project-local file (`.claude/settings.local.json`). Project-local permissions override (not merge
with) user-level permissions, so maintaining a separate project allow list causes the user-level
rules to be silently ignored.
