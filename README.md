# Phoenix Engine Plugin for Claude Code

A comprehensive Claude Code plugin for developing the Phoenix Engine — a cross-platform C++ game engine targeting Linux and Windows.

## Installation

```bash
# Clone the plugin
git clone git@github.com:RyanBuehler/PhoenixClaudePlugin.git

# Add to Claude Code
claude plugin add ./PhoenixClaudePlugin
```

## Agents (21)

Specialized subagents for different aspects of engine development.

### Core Development
| Agent | Description |
|-------|-------------|
| `invoke-code-reviewer` | C++ code review — bugs, UB, style, modern C++23 |
| `invoke-const-agent` | Const correctness fixes |
| `invoke-format-agent` | clang-format wrapper |
| `invoke-lint-agent` | clang-tidy static analysis |
| `invoke-style-agent` | Formatting/linting tool maintenance |
| `invoke-python-reviewer` | Python code review |
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
| `invoke-portability-agent` | Cross-platform portability scanning |

### Testing & Debugging
| Agent | Description |
|-------|-------------|
| `invoke-test-author` | Test setup with Trials framework |
| `invoke-test-engineer` | Test strategy and debugging |
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

## Commands (7)

Slash commands for common workflows.

| Command | Description |
|---------|-------------|
| `/build` | Build the project in Release configuration |
| `/test` | Run the test suite via CTest |
| `/format` | Format staged C++ files and verify |
| `/lint` | Run clang-tidy on changed files |
| `/screenshot` | Capture a screenshot from the engine |
| `/verify` | Full CI-mirror: build + format + lint + test |
| `/scaffold-module` | Create a new module using `Tools/create_module.py` |

## Hooks

| Hook | Event | Description |
|------|-------|-------------|
| Commit guard | PreToolUse (git commit) | Runs format and lint checks before allowing a commit |

## References (5)

Quick-reference documents for agents to consult.

| Reference | Description |
|-----------|-------------|
| `modern-cpp.md` | C++20/23/26 features and migration patterns |
| `modern-cmake.md` | Target-based builds, presets, generator expressions |
| `modern-python.md` | Python 3.12+ features for build tooling |
| `modern-vulkan.md` | Dynamic rendering, descriptor buffers, sync2 |
| `cpp-portability.md` | Cross-platform pitfalls and portable solutions |

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
