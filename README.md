# Phoenix Engine Plugin for Claude Code

A comprehensive Claude Code plugin for developing the Phoenix Engine — a cross-platform C++ runtime targeting Linux and Windows.

## Installation

```
/plugin install phoe --marketplace RyanBuehler/PhoenixClaudePlugin
```

## Always-on rules

`references/core-rules.md` holds the rules every session needs — conduct, branches and worktrees,
searching, the verification gate, and the codebase rules the repository docs do not state.
`hooks/core-rules.py` loads it into every session (on startup, resume, `/clear` and compaction) and
into every subagent except the built-in Explore and Plan, because Claude Code does not load a
`CLAUDE.md` from a plugin root. Rules used by one workflow live in that skill or in `references/`.

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
| `invoke-shader-expert` | Slang/SPIR-V shaders — compile errors, validation, performance |

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
| `core-rules.py` | SessionStart, SubagentStart | Loads `references/core-rules.md` into context |
| `branch-worktree-check.py` | PreToolUse (Bash) | Branches are `<type>/<label>`, within 40 characters, created through a worktree |
| `bash-guard.py` | PreToolUse (Bash) | Denies `cd` + `git`, root-wide sweeps, risky `git grep` forms, and load generators |
| `push-gate.py` | PreToolUse (Bash) | Checks git identity and push credentials before `git push` and `gh pr create` |
| `attribution-check.py` | PreToolUse (Bash) | Refuses AI attribution trailers and banners in published text |
| `agent-registry-tracker.py` | PostToolUse (Bash) | Records which session or job created or edited each PR, for the `agents` skill |

## References

Documents agents consult while working, in `references/`: C++, Python and Vulkan guides
(`modern-cpp.md`, `modern-python.md`, `modern-vulkan.md`), portability (`cpp-portability.md`),
formatter and linter mechanics (`tooling.md`), machine load (`machine-load.md`), the shared
challenge steps (`challenge-workflow.md`, `implementer-brief.md`, `dispatch-briefs.md`,
`parallel-integration.md`, `concluding-work.md`), and the always-on `core-rules.md`.

Code style is **not** here: `Docs/StyleGuide.md` lives in the Phoenix repository, since it is
agent-agnostic, alongside `Docs/Patterns.md` and `Docs/Lexicon.md`.

## License

MIT
