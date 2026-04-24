# Phoenix Engine — Architecture Notes

## Hard Requirements

- **NEVER mention Claude Code in commit messages.** No "Generated with Claude Code", no Co-Authored-By Claude, nothing. Commit messages should look like they were written by a human developer.
- **Never combine `cd` and `git` in a compound command** (e.g. `cd /some/dir && git status`). Changing into an untrusted directory before running git exposes you to bare repository attacks where a malicious `.git` config can execute arbitrary code. Always run git commands using absolute paths or from the known working directory.

## Agent Conduct

### Search before claiming the codebase lacks something

Before asserting the codebase does not contain a feature, type, pattern, or convention, search the codebase first using Grep, Glob, or an equivalent search tool. This rule is a hard directive, not a suggestion.

Guarded failure modes include any phrasing of "Phoenix has no X", "there is no existing Y", "this would be the first Z", and "we lack support for W". The rule applies to PR review replies, architectural recommendations, design discussions, and any communication where the codebase's current state is being characterized.

If the search returns no results, say "I did not find X" rather than "X does not exist". One statement is an observation; the other is a claim that a reviewer can falsify.

Minimal example: before claiming Phoenix lacks reflection, run `grep -r reflection Core/ Modules/` — Phoenix in fact ships a reflection system in `Core/Public/Reflection/Reflective.cppm`, and an unchecked absence claim on a public PR thread has to be walked back by hand.

### Verify review-comment code claims before acting

When a code-review comment names a specific C++ construct, verify the construct is actually present on the referenced line or in the immediate neighborhood before making any change. GitHub diff views shift line numbers across PR updates, and reviewers occasionally conflate related concepts — the cited line number is a hint, not a contract.

Constructs that warrant this verification include:

- RTTI (`dynamic_cast`, `typeid`, `type_info`)
- `reinterpret_cast`, `const_cast`, C-style casts
- Exceptions (`throw`, `try`, `catch`, `noexcept`)
- Macros
- Virtual inheritance
- Templates, concepts, coroutines
- C++20 module keywords (`import`, `export`, `module`)

If the cited construct is absent from the referenced line and its neighborhood, do not guess at intent and do not make a change that might not match. Reply with:

> "I do not see `<construct>` on `<file>:<line>`; the line uses `<actual-construct>`. Did you mean X, or were you looking at an earlier draft?"

Blind action on a misread review comment ships a wrong change; asking once is cheap.

### Working directory: use absolute paths or an explicit `cd` per Bash call

Every Bash invocation starts a fresh shell at the user's primary working directory. A `cd` from a prior Bash call does **not** carry forward. Mentally tracking "which directory am I in" across separate Bash calls silently runs commands in the wrong tree.

Use one of the two safe patterns on every invocation:

- **Absolute paths for every argument.** `ls /absolute/path/to/worktree/build-editor-debug`.
- **Explicit `cd` prefix in the same invocation.** `cd /absolute/path/to/worktree && cmake --build build-dispatch-verify --target Dispatch`.

Failure modes this rule prevents include running cmake or ninja in the wrong tree, sourcing the wrong `.env`, editing the wrong file, and grepping a stale copy that does not reflect pending edits.

Worktrees are the highest-risk setting: the main repo and `.claude/worktrees/<branch>` are two independent checkouts. A cmake build invoked in the wrong tree can report success against code that does not include the current changes, masking a compile failure that only surfaces in CI. Whenever a session has an active worktree, every Bash call that touches the checkout must name the worktree path explicitly.

The `cd`-and-`git` prohibition in **Hard Requirements** is a stricter variant of this rule: git in particular must never be paired with a `cd` into an untrusted directory. For non-git commands the `cd` prefix is fine and is the preferred form when arguments are relative.

## Branch & Worktree Workflow

All work happens on a dedicated branch in a dedicated worktree. Branch names are `<type>/<label>` where both segments are lowercase kebab-case (`^[a-z0-9][a-z0-9-]*$`). Slash-less branch names are rejected.

Common types:

- `challenge/<label>` — Crucible challenge work
- `bug/<label>` — Crucible bug fixes
- `doc/<label>` — documentation-only changes
- `ci/<label>` — CI and tooling changes
- `misc/<label>` — one-off work that doesn't fit the above

Prefix the label with the affected system or module when it helps reviewers, e.g. `challenge/crucible-update-ui`, `bug/windows-liaison-fix-focus`, `doc/branch-workflow`. The system prefix is convention only; the hook does not enforce a specific list.

Create every branch via worktree, from the main repo root:

    git worktree add .claude/worktrees/<type>-<label> -b <type>/<label>

The worktree path uses dashes where the branch uses slashes. Plain `git checkout -b`, `git switch -c`, and `git branch <name>` are blocked at tool-use time by `hooks/branch-worktree-check.py`.

Remove a worktree when done (the branch stays until the user deletes it):

    git worktree remove .claude/worktrees/<type>-<label>

`/phoe:reset-workspace` prunes worktrees whose branch is `[gone]`. Blocked branches and their worktrees are preserved for human resumption.

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

### When to create a subsystem

A subsystem is a **projection** of a module's public API — it selects and names the subset of
operations a specific consumer should see. Subsystems do not expand a module's API surface,
introduce new types of their own, or wrap a module reference for handoff. Multiple subsystems
may front the same module (e.g. `Sonic` exposing `ISFX` for gameplay and `IMusic` for score).
If a proposed subsystem adds new types or methods the module does not expose, it is a module,
not a subsystem.

## Subsystem Interface Design

Subsystem interfaces must be **intent-based**, not lazy accessors. Every method on an
`ISubsystem` should describe an action a consumer performs (`PostEntry`, `SubmitTask`,
`RegisterAccount`), not hand out a reference to the underlying system (`GetLedger`,
`GetInstance`).

The app owns its systems directly (e.g. Editor owns its `Ledger`). Other modules participate
through the subsystem protocol, not by grabbing a reference to the internals.

Follow `IArbiterSubsystem` as the canonical example: it exposes `SubmitTask` /
`WaitForCompletion` rather than `GetArbiter`. Interfaces that degenerate into a single
`GetX()` accessor are a code smell — replace them with the operations the consumer actually
needs to perform.

**No object handoff across modules.** Module A must not receive a reference or pointer to a
concrete type owned by Module B. Cross-module communication goes through subsystem interfaces
only — never by threading `FooModule&`/`FooModule*` across the boundary.

**Internals-returning accessors are a smell everywhere, not just in subsystems.** A `GetFoo()`
that hands back a reference to an owned member bypasses the owner's invariants. Expose
operations (`ApplyFoo`, `PostFoo`) instead.

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
- `APPLICATION` cache variable selects which app to build: `Editor`, `Game`, `Vigil`, `Crucible`, `Forge`, or `Minimal`

## CI

The Linux CI workflow (`.github/workflows/ci.yml`) runs three sequential jobs on PR:

1. **Linux: Modularity** — Validates Engine builds with only Core (Minimal application)
2. **Linux: Build & Test (Incremental)** — Builds all 5 apps (Editor, Vigil, Game, Crucible, Forge) with ccache. Runs `CORE_TRIAL|PLUGIN_TRIAL|APP_TRIAL` from Editor (most module coverage), then `APP_TRIAL` only from Vigil, Crucible, and Forge (app-specific tests). Game is build-only (all its tests are covered by Editor).
3. **Linux: Format & Lint** — Checks formatting and runs clang-tidy

Jobs run in order; failure in any job skips subsequent jobs.

Test labels are derived from `MODULE_CATEGORY`, a target property set automatically from the module's directory: `Applications/` → APP_TRIAL, `Plugins/` → PLUGIN_TRIAL, `Modules/` → CORE_TRIAL. Benchmarks are skipped at runtime by default — they use `BENCHMARK_TRIAL` in the Trials framework and run only when `--type benchmark` is passed to the test executable.

## Code Guidelines

For all code style and design practices — formatting, naming, language features, comments,
TODOs, error handling, design practices — follow `references/style-guide.md`. For tooling
mechanics (formatter/linter configuration, commands, troubleshooting), see
`references/tooling.md`.

After changing C/C++ code, run `python3 Tools/format.py --files=staged` to apply
`clang-format`, then `python3 Tools/format.py --files=staged -error` to verify formatting.
Run `python3 Tools/tidy.py` to check for clang-tidy warnings. If the script reports a missing
compilation database, regenerate it once per build directory with `python3 Tools/tidy.py
--compdb` (optionally keeping your `--filter` arguments); this leaves
`build/compile_commands.json` in place for subsequent tidy runs. Test sources matching
`*Trials.cpp` may be skipped by passing `--filter *Trials.cpp`. Note: the `build/` directory
that `Tools/tidy.py --compdb` creates is a tooling-scratch dir for the compilation database
only — it is *not* the project's Forge-managed build dir (which is always profile-suffixed,
e.g. `build-editor-debug/`). Don't run cmake/ctest against `build/`; only `Tools/tidy.py`
reads from it.

## Crucible Lifecycle Reference

The plugin's Crucible workflows operate on three task types. Match status names exactly — the CLI
rejects unknown statuses, and using the wrong terminal status (e.g. `merged` for a bug, `done` for
a challenge) causes silent reconciliation failures across `/phoe:implement`, `/phoe:execute`,
`/phoe:bugfix`, and `/phoe:finalize`.

| Task type | Statuses (in order)                                              | Terminal |
|-----------|------------------------------------------------------------------|----------|
| Challenge | `todo` → `implementing` → `review` → `merged` (or `blocked`)     | `merged` |
| Bug       | `todo` → `implementing` → `review` → `done`                      | `done`   |
| Saga      | *(no status — tracks collective challenge progress)*             | n/a      |

CLI shape is parallel — `crucible challenge move --label=<L> <status>` /
`crucible bug move --label=<L> <status>`. When writing a workflow that accepts either, branch on
type early and use the type-correct verbs throughout; do not paper over the difference.

Branch naming follows the same split: `challenge/<label>` for challenges, `bug/<label>` for bugs.
Worktrees follow at `.claude/worktrees/<type>-<label>` (slashes converted to dashes).

## Labels and Identifiers

- Use `Label` (not `string`/`string_view`) for keys, registry lookups, dispatch tokens,
  event/action names — anything used as identity. Raw strings stay for textual data
  (logs, UI text, file contents, parsed tokens).
- Pass `Label` by value; never `const Label&`. Convert at API boundaries with
  `ToCString()` / `ToString()`.
- When registering into a module's registries, use that module's wrapper (e.g.
  `Input::Label`) so the hash carries the module signature.

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

## pImpl Decision Gate

Never introduce pImpl (`std::unique_ptr<Impl>` + forward-declared `Impl` struct) in new Phoenix types unless at least one of the following holds:

1. **ABI stability across a dynamic linker boundary** where consumers do not rebuild when the type's representation changes. This is what pImpl is actually for in library codebases.
2. **A private type that is genuinely forbidden in the public TU set** — a vendored third-party SDK header that drags in incompatible macros, or an OS header whose leakage would poison callers.
3. **Runtime strategy or state polymorphism** where `Impl` will have multiple concrete subclasses selected at construction time.

"Header weight" — avoiding transitive includes like `Json/JsonValue.h` — is **NOT** a sufficient justification in this codebase. `import Phoenix;` already re-exports the standard surface, the engine rebuilds everything on every change, and every peer shared-lib class (Engine, Ledger, LedgerModule, Archive, Vigil, Soulforge, WorkQueue, GameCycleGraph) uses direct value members. Matching habits from ABI-stable library projects pattern-matches on the wrong codebase shape.

If none of the three justifications applies, pick one of:

- **(a) Flatten to direct value members.** Default choice. The type goes straight on the class like every peer.
- **(b) Forward-declare + `std::unique_ptr<T>` for one specific heavy field.** Use when exactly one member is genuinely heavy; do not upgrade this into a full pImpl.
- **(c) Request a bypass on the PR.** If the work genuinely needs pImpl and does not match (1)–(3), say so in the PR description with the justification so the reviewer can evaluate.

## clang-tidy NOLINT Policy

NOLINT is rare. Every use must carry a one-line justification naming the specific reason neither a code change nor a `.clang-tidy` tuning was viable.

Decision order, strictly:

1. **Fix the code.** Restructure so the check does not fire. This is the default answer.
2. **Tune `.clang-tidy`.** If a whole category of false positives is firing across the codebase, disable or narrow the check in configuration. A check that fires on every file is the wrong check for the project; its noise belongs in configuration, not in comments sprinkled through source.
3. **Narrow NOLINT, last resort only.** A single inline `// NOLINT(check-name): <one-line reason>` on the specific line, nowhere wider.

Hard forbiddings:

- **No file-wide `NOLINTBEGIN`/`NOLINTEND` blocks for style-level checks.** If `readability-convert-member-functions-to-static` (or any similar style check) is firing on every file, the check is wrong for the project and belongs in `.clang-tidy` configuration, not wrapped around whole translation units.
- **No multi-line comment rationale.** One short line or the NOLINT does not ship. If the justification needs a paragraph, the code needs to be restructured instead.

Canonical legitimate case: the `std::byte*` ↔ `char*` I/O boundary. Bridging `std::byte` buffers to string or stream APIs requires `reinterpret_cast`, and `cppcoreguidelines-pro-type-reinterpret-cast` is correctly disabled at the repository level; any remaining narrow casts go through one of the project's byte/char helpers with a single-line NOLINT at the helper site.

## Build Commands

- **NEVER** use `-j$(nproc)` or `-j` with cmake. Always use `cmake --build <dir> --parallel`. The `$()` subshell triggers permission prompts and `-j` is generator-specific.
- **Worktrees do not share build directories with the main workspace.** CMake caches absolute paths to the source tree, so each git worktree needs its own `/phoe:build` run (which configures + builds via Forge's profile system into the worktree's own `build-editor-debug/` etc.). Do not symlink or reuse the main workspace's build dirs inside a worktree — the cached source paths will point at the wrong tree and produce subtly broken artifacts.

## Build & Test Verification

- Do NOT run builds or tests after every code change. Run the full
  verification sequence (`/phoe:verify`) **before committing** as part of the
  development workflow. Passing `/phoe:verify` is a mandatory precondition for
  every commit; a commit made without it is incomplete work. This overrides any
  TDD or verification-before-completion guidance from other skills.

## Push & Pull Request Workflow

Pushing and PR creation are shared-state, outside-visible actions. Never take
them autonomously.

Before running `git push` or `gh pr create`:

1. **Verify git credentials are configured and authenticate against the remote.**
   Run `git config user.name`, `git config user.email`, and
   `git ls-remote <remote> HEAD` to confirm auth works. If credentials are
   missing, expired, or fail against the remote, stop and surface the failure
   to the user — do not attempt the push.
2. **Ask the user for explicit confirmation.** Even when verification has
   passed and credentials are valid, always ask before pushing or opening a
   pull request. Present what you intend to push (branch, commits, target
   remote) and wait for an explicit go-ahead. A prior approval does not carry
   forward to later pushes.
- To verify compilation and run all tests locally, mirror the CI pipeline.
- It is mandatory to execute the full verification suite before committing. Run
  `/phoe:verify` — it drives Forge through build + format + lint + test using the
  active profile and the environment-suffixed tool paths, producing the same
  pass/fail signal as the `Linux: Build & Test (Incremental)` CI job. Do not
  invoke cmake/ctest directly; a bare `build/` directory does not exist in this
  project.
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
build-<profile>/bin/editor --console-pipe=/tmp/phoenix-console.fifo

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
xvfb-run build-<profile>/bin/editor --aurora.screenshot.exit
```

## Reference Documents

The `references/` directory contains quick-reference guides that agents can consult:

- `modern-cpp.md` — C++20/23/26 features, idioms, and migration patterns
- `modern-cmake.md` — Target-based builds, presets, FetchContent, generator expressions
- `modern-python.md` — Python 3.12+ features, pathlib, type hints, CLI patterns
- `modern-vulkan.md` — Dynamic rendering, descriptor buffers, synchronization2, timeline semaphores
- `cpp-portability.md` — Cross-platform pitfalls, fixed-width types, alignment, char signedness
- `style-guide.md` — Authoritative code style and design guide (formatting, naming, comments, design practices)
- `tooling.md` — Formatter/linter configuration and command reference

## Permissions

Add new tool permissions to the **user-level** settings (`~/.claude/settings.json`), not the
project-local file (`.claude/settings.local.json`). Project-local permissions override (not merge
with) user-level permissions, so maintaining a separate project allow list causes the user-level
rules to be silently ignored.
