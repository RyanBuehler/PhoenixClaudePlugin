# Phoenix Engine Plugin for Claude Code

A comprehensive Claude Code plugin for developing the Phoenix Engine — a cross-platform C++ game engine targeting Linux and Windows.

## Installation

```bash
# Clone the plugin
git clone git@github.com:RyanBuehler/PhoenixClaudePlugin.git

# Add to Claude Code
claude plugin add ./PhoenixClaudePlugin
```

## Agents (16)

Specialized subagents for different aspects of engine development.

### Core Development
| Agent | Description |
|-------|-------------|
| `invoke-code-reviewer` | C++ code review — bugs, UB, style, portability, modern C++23 |
| `invoke-lint-agent` | clang-tidy static analysis |
| `invoke-include-analyzer` | IWYU, circular includes, PCH optimization |

### Architecture & Design
| Agent | Description |
|-------|-------------|
| `invoke-systems-designer` | Module architecture, interface design |
| `invoke-rendering-designer` | Render graph, material system architecture |
| `invoke-build-engineer` | CMake, CI/CD, cross-platform builds |

### Graphics & Rendering
| Agent | Description |
|-------|-------------|
| `invoke-vulkan-agent` | Vulkan API, synchronization, descriptors |
| `invoke-shader-expert` | GLSL/SPIR-V compilation and debugging |

### Platform
| Agent | Description |
|-------|-------------|
| `invoke-linux-agent` | Linux/POSIX development |
| `invoke-windows-agent` | Windows/Win32 development |

### Testing & Debugging
| Agent | Description |
|-------|-------------|
| `invoke-test-engineer` | Test setup, strategy, coverage, and debugging |
| `invoke-debugger-agent` | GDB/LLDB, core dumps, breakpoints |
| `invoke-memory-agent` | Memory debugging, sanitizers, Valgrind |

### Performance
| Agent | Description |
|-------|-------------|
| `invoke-perf-agent` | CPU profiling and optimization |
| `invoke-concurrency-agent` | Thread safety, lock-free algorithms |

### Capture
| Agent | Description |
|-------|-------------|
| `invoke-screenshot-agent` | Engine screenshot capture and analysis |

## Commands (12)

Slash commands for common workflows.

| Command | Description |
|---------|-------------|
| `/plan` | Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges |
| `/implement` | Pick up a Crucible Challenge by label and implement it end-to-end with verification |
| `/build` | Build the project in Release configuration |
| `/test` | Run the test suite via CTest |
| `/format` | Format staged C++ files and verify |
| `/lint` | Run clang-tidy on changed files |
| `/screenshot` | Capture a screenshot from the engine |
| `/verify` | Full CI-mirror: build + format + lint + test |
| `/scaffold-module` | Create a new module using `Tools/create_module.py` |
| `/frontend-design` | Generate interactive HTML playground for iterating on UI layout and styling |
| `/reset-workspace` | Clean up the workspace — resolve unstaged files, switch to main, pull latest, prune branches |
| `/edit-plugin` | Edit the PhoenixClaudePlugin source — add/modify commands, agents, hooks, skills, or references and bump the version |

## Skills (2)

Auto-activating skills that trigger based on context.

| Skill | Description |
|-------|-------------|
| `frontend-validate` | Auto-captures and evaluates screenshots after UI code changes; annotation playground for marking issues |
| `trace-debug` | Auto-activates when investigating reproducible Phoenix bugs; instruments with Scribe breadcrumbs and bisects the suspect region by judgment |

## Hooks

| Hook | Event | Description |
|------|-------|-------------|
| Commit guard | PreToolUse (git commit) | Runs format and lint checks before allowing a commit |

## References (6)

Quick-reference documents for agents to consult.

| Reference | Description |
|-----------|-------------|
| `modern-cpp.md` | C++20/23/26 features and migration patterns |
| `modern-cmake.md` | Target-based builds, presets, generator expressions |
| `modern-python.md` | Python 3.12+ features for build tooling |
| `modern-vulkan.md` | Dynamic rendering, descriptor buffers, sync2 |
| `cpp-portability.md` | Cross-platform pitfalls and portable solutions |
| `code-style.md` | Formatting stack, clang-format/clang-tidy config, tool architecture |

## Project Conventions

- **No exceptions** — `try`, `catch`, `throw`, `noexcept` are forbidden
- **Tab indentation** — C++, Python, CMake all use tabs
- **PascalCase** — types, functions, and variables
- **`m_` prefix** — private members
- **`#pragma once`** — all headers
- **Platform isolation** — no `#ifdef` guards; platform code in liaison modules
- **Named namespaces only** — anonymous namespaces break unity builds

## License

MIT
