# Phoenix Engine Plugin for Claude Code

A comprehensive Claude Code plugin for developing the Phoenix Engine — a cross-platform C++ game engine targeting Linux and Windows.

## Installation

```bash
# Clone the plugin
git clone git@github.com:RyanBuehler/PhoenixClaudePlugin.git

# Add to Claude Code
claude plugin add ./PhoenixClaudePlugin
```

## Agents (14)

Specialized subagents for different aspects of engine development.

### Core Development
| Agent | Description |
|-------|-------------|
| `invoke-code-reviewer` | C++ code review — bugs, UB, style, portability, modern C++23 |
| `invoke-lint-agent` | clang-tidy static analysis plus include/module-import dependency hygiene |
| `invoke-spec-reviewer` | Crucible challenge spec compliance — nothing missing, nothing extra |

### Architecture & Design
| Agent | Description |
|-------|-------------|
| `invoke-systems-designer` | Module architecture, interface design |
| `invoke-rendering-designer` | Render graph, material system architecture |
| `invoke-build-engineer` | Forge profiles, CI/CD, cross-platform builds |

### Graphics & Rendering
| Agent | Description |
|-------|-------------|
| `invoke-vulkan-agent` | Vulkan API, synchronization, descriptors |
| `invoke-shader-expert` | GLSL/SPIR-V compilation and debugging |

### Platform
| Agent | Description |
|-------|-------------|
| `invoke-platform-agent` | Linux/POSIX and Windows/Win32 development, liaison modules |

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

## Skills (21)

Every workflow is a skill under `skills/<name>/SKILL.md`, invoked as `/phoe:<name>`.

### Workflows you start
These set `disable-model-invocation: true`, so they cost no context until you type them.

| Skill | Description |
|-------|-------------|
| `/phoe:plan` | Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges |
| `/phoe:execute` | Autonomously execute N Crucible challenges via subagents |
| `/phoe:frontend-design` | Generate an interactive HTML playground for iterating on UI layout and styling |
| `/phoe:scaffold-module` | Create a new module using `Tools/create_module.py` |
| `/phoe:gc-worktrees` | Remove worktrees whose branch has provably landed on origin/main — dry-run first, PR-confirmed |
| `/phoe:edit-plugin` | Edit this plugin and bump its version |

### Workflows either you or the model start
| Skill | Description |
|-------|-------------|
| `/phoe:implement` | Pick up a Crucible Challenge and implement it end-to-end with verification |
| `/phoe:bugfix` | Pick up a Crucible Bug and fix it end-to-end with verification |
| `/phoe:build` | Build the engine or a tool executable through Forge |
| `/phoe:test` | Run the trial suite through Forge |
| `/phoe:verify` | Full CI-mirror: audits, build, format, lint, test |
| `/phoe:format` | Format changed C++ files and verify |
| `/phoe:lint` | Run clang-tidy on changed files |
| `/phoe:screenshot` | Capture a screenshot from the engine |

### Auto-activating
| Skill | Description |
|-------|-------------|
| `crucible` | Any Crucible saga/challenge/bug question or action |
| `agents` | Which background job owns a PR, branch, or worktree |
| `audit` | Convention-drift audit of cold files or modules |
| `pr-fixup` | Address review feedback on an open PR |
| `trace-debug` | Scribe-breadcrumb bisection of a reproducible bug |
| `ui-design-review` | Mosaic UI architecture and convention review |
| `icon` | Add, replace, or audit Phosphor icons in the Editor |

## Hooks

| Hook | Event | Description |
|------|-------|-------------|
| Commit guard | PreToolUse (git commit) | Runs format and lint checks before allowing a commit |

## References (6)

Quick-reference documents for agents to consult.

| Reference | Description |
|-----------|-------------|
| `modern-cpp.md` | C++20/23/26 features and migration patterns |
| `modern-python.md` | Python 3.12+ features for build tooling |
| `modern-vulkan.md` | Dynamic rendering, descriptor buffers, sync2 |
| `cpp-portability.md` | Cross-platform pitfalls and portable solutions |
| `tooling.md` | Formatter/linter configuration and command reference |
| `dispatch-briefs.md` | Dispatch brief format |

Code style is **not** here: `Docs/StyleGuide.md` lives in the repository, since it is agent-agnostic.

## Project Conventions

- **No exceptions** — `try`, `catch`, `throw`, `noexcept` are forbidden
- **Tab indentation** — C++ and Python use tabs
- **PascalCase** — types, functions, and variables
- **`m_` prefix** — private members
- **`#pragma once`** — all headers
- **Platform isolation** — no `#ifdef` guards; platform code in liaison modules
- **Named namespaces only** — anonymous namespaces break unity builds

## License

MIT
