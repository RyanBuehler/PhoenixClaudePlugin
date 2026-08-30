# Phoenix — agent operating guide

## Hard Requirements

- **NEVER mention Claude Code in commit messages.** No "Generated with Claude Code", no Co-Authored-By Claude, nothing. Commit messages should look like they were written by a human developer.
- **Never push or open a pull request without explicit confirmation.** See [Push & Pull Request Workflow](#push--pull-request-workflow).
- **NEVER manufacture machine load without explicit, per-instance user permission.** No CPU spin loops, fork bombs, memory balloons, disk fillers, or parallel-job storms sized beyond the host. This machine is shared with the user and with other agent sessions, and orphaned load is misattributed to whoever runs next. See [Never manufacture machine load](#never-manufacture-machine-load).
- **Never combine `cd` and `git` in a compound command** (e.g. `cd /some/dir && git status`). Changing into an untrusted directory before running git exposes you to bare repository attacks where a malicious `.git` config can execute arbitrary code. Use `git -C <path>` or run from the known working directory.
- The repository's own `CLAUDE.md` is binding where it speaks; this file adds what an agent needs and the codebase has no reason to carry.

## Where the rules live

Agent material lives here, not in the codebase — that separation is the whole point of the
plugin. This file and `references/` carry how to work: conduct, workflow, and the domain
references an agent consults. The repository carries what the codebase is.

The style guide is the deliberate exception. It is agent-agnostic — a contributor who never runs
an agent needs it just as much — so it lives in the repository and the plugin does not keep a
copy.

| Subject | Authority |
|---|---|
| Agent conduct, workflow, verification, pushing | this file |
| Code style, naming, comments, design practices | `Docs/StyleGuide.md` (in the repository) |
| Formatter and linter mechanics | `${CLAUDE_PLUGIN_ROOT}/references/tooling.md` |
| C++, Python, Vulkan, portability references | `${CLAUDE_PLUGIN_ROOT}/references/` |
| Architecture, module layout, ownership tiers | the repository's `CLAUDE.md` |
| Build, test, verify | `Applications/Forge/`, `Docs/Forge_DD.md`, `/phoe:verify` |
| Blessed and banned terms | `Docs/Lexicon.md` |

The repository's `CLAUDE.md` and `Docs/StyleGuide.md` bind. If this file ever contradicts one of
them, this file is the stale one and the fix belongs here.

## Agent Conduct

### Keep responses short and plain

Answer the question that was asked, at the length that answer needs. Cut the restatement of the request, the options you are not taking, and the recap of work the user just watched you do.

Write plainly. No jargon where a common word works, no extended metaphors, no pseudo-academic register (*fundamentally*, *it is worth noting that*, *this exemplifies a broader pattern*). Technical precision is not verbosity — name the type, the file, the failure. It is the padding around them that gets cut.

### Bracket the work: one sentence before, the outcome first after

Before the first tool call of a turn, say in one sentence what you are about to do. One sentence, not a plan: the user needs enough to stop you, not a design to read.

When you finish, lead with the raw outcome — what happened, what state the tree or the PR is in, what failed. Caveats, rationale, and next steps come after it. A report that opens with process and buries the result makes the user read to the end to learn whether it worked.

### Search before claiming the codebase lacks something

Before asserting the codebase does not contain a feature, type, pattern, or convention, search the codebase first using Grep, Glob, or an equivalent search tool. This rule is a hard directive, not a suggestion.

Guarded failure modes include any phrasing of "Phoenix has no X", "there is no existing Y", "this would be the first Z", and "we lack support for W". The rule applies to PR review replies, architectural recommendations, design discussions, and any communication where the codebase's current state is being characterized.

If the search returns no results, say "I did not find X" rather than "X does not exist". One statement is an observation; the other is a claim that a reviewer can falsify.

Minimal example: before claiming Phoenix lacks reflection, run `grep -r reflection Engine/Core/ Engine/Modules/` — Phoenix in fact ships a reflection system in `Engine/Core/Public/Reflection/Reflective.cppm`, and an unchecked absence claim on a public PR thread has to be walked back by hand.

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

- **Absolute paths for every argument.** `ls /absolute/path/to/worktree/Applications/Forge/.forge/editor-debug`.
- **Explicit `cd` prefix in the same invocation.** `cd /absolute/path/to/worktree && forge build editor-debug`.

Failure modes this rule prevents include building the wrong tree, sourcing the wrong `.env`, editing the wrong file, and grepping a stale copy that does not reflect pending edits.

Worktrees are the highest-risk setting: the main repo and `.claude/worktrees/<branch>` are two independent checkouts. Forge resolves its project root from where it runs, so a build launched from the wrong tree reports success against code that does not contain your changes, masking a failure that only surfaces in CI. Whenever a session has an active worktree, every Bash call that touches the checkout must name the worktree path explicitly.

The `cd`-and-`git` prohibition in **Hard Requirements** is a stricter variant of this rule: git in particular must never be paired with a `cd` into an untrusted directory. For non-git commands the `cd` prefix is fine and is the preferred form when arguments are relative.

### Never manufacture machine load

Do not spawn CPU load generators, busy-wait spinners, fork bombs, memory balloons, disk fillers, or parallel-job storms sized beyond the host. This is a hard prohibition, not a preference, and it requires **explicit user permission for each instance**. "Go debug this flake" is not permission to load the machine. Permission granted once does not carry to the next flake, the next command, or the next session.

The rule covers the class, not one idiom. All of these are prohibited without permission:

- **CPU** — `while :; do :; done` spinners, `yes > /dev/null`, `stress`/`stress-ng`, deliberately oversubscribed `--parallel`/`-j` values.
- **Memory** — balloon allocations intended to force pressure or swapping.
- **Disk** — fillers written to exhaust free space or saturate I/O.
- **Process** — fork storms, and running many heavy builds or test suites concurrently to "see what breaks".

**Why this is a hard rule: the blast radius crosses sessions.** The host is shared with the user and with other agents working in sibling worktrees. Load you create is invisible to them, outlives the command that started it, and gets attributed to whoever runs next — they will spend their session triaging a phantom regression against their own diff.

Observed on the development host (2026-07-27): 80 orphaned spinners in two abandoned batches, aged 20h and 29h, had burned 339.6 CPU-hours between them. Load average on a 16-core machine reached 84.29, roughly 5x oversubscribed, leaving real work about 17 percent of the machine. The concrete damage to other sessions:

- `forge lint` has a per-file cap. Starvation turns that into a hard red carrying **no diagnostic at all**. A two-file lint went 1m31s to 5m16s and failed.
- `forge verify` builds stretched to ~38 minutes.
- Wall-clock-threshold trials reddened constantly, and one abandoned experiment left `/tmp` residue that deterministically broke an unrelated module's trials.

**A trailing `kill $LOADPIDS` is not a cleanup contract.** It runs only if the command reaches its end. When the wrapping shell is interrupted, times out, or is moved to the background by the harness, the generators are orphaned, reparented to `systemd --user`, and run forever. That is exactly how the incident above happened.

Where the user has explicitly permitted load testing, the generator must be **self-limiting**, so that no cleanup step is required for it to die:

```bash
# Each generator carries its own deadline: -k forces SIGKILL if SIGTERM is ignored.
# Killing the wrapping shell at any point cannot outlive the timeout.
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM   # armed first; courtesy only, NOT sufficient alone
for _ in $(seq 1 4); do timeout -k 5 30 sh -c 'while :; do :; done' & done
wait
```

The `timeout` is what makes this safe — the `trap` is a courtesy that never runs if the shell is SIGKILLed. Arm it before the first job, so an interrupt during startup still finds a handler, and aim it at `jobs -p` rather than `kill 0`: the latter signals the whole process group and would take an interactive shell down with it. Prefer the smallest load and shortest deadline that reproduces the effect, and tell the user what you are about to start before you start it.

### Diagnosing a starved host

Before concluding that a lint timeout, a build slowdown, or a wall-clock trial failure is caused by your own diff, check whether the machine is starved:

```bash
uptime                                                        # load average vs. core count
ps -eo pid,ppid,etime,time,pcpu,comm --sort=-pcpu | head -20  # who is burning CPU, and for how long
```

Read the signals this way:

- Load average well above the core count means your timings mean nothing. Re-run when it drops rather than chasing the result.
- A `timeout after Ns` that carries **no diagnostics** is starvation, not a finding. Real lint findings come with text.
- A long `etime` on a process whose parent is `systemd --user` (PPID 1 reparenting) is an orphan from an abandoned session, not something the current work started.

If you find orphaned load generators, report them to the user with their PIDs and ages and ask before killing anything — they may belong to a session that is still running.

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

`claude agents` background sessions and `isolation: worktree` sub-agents also live under `.claude/worktrees/` with Claude-generated names — `branch-worktree-check.py` still enforces branch rules inside each.

## Background Sessions (`claude agents`)

`claude agents` (Claude Code v2.1.139+) manages background sessions — each row is its own process and quota draw. Start with `claude --bg "<prompt>"` or `/bg`. On the session's first write, Claude Code moves it to `.claude/worktrees/<auto-name>` automatically, so parallel sessions never share `build-*/`. The worktree is deleted with the session — push/merge first.

## Sub-agent Worktree Isolation

The build-touching `agents/invoke-*.md` definitions (`build-engineer`, `test-engineer`, `lint-agent`, `memory-agent`, `perf-agent`, `debugger-agent`, `concurrency-agent`, `vulkan-agent`, `shader-expert`, `platform-agent`) set `isolation: worktree` so concurrent `Agent()` calls never collide on `build-*/`. The four design/review agents (`code-reviewer`, `spec-reviewer`, `systems-designer`, `rendering-designer`) do not — they read but don't build, and Claude Code auto-cleans an isolated worktree when the agent makes no changes.

## Code Guidelines

**Before writing any C++**, read the repository's `Docs/StyleGuide.md` — formatting, naming,
language features, comments, TODOs, and design practices, all of it binding — and the
conventions in the repository's `CLAUDE.md` that override it. For tooling mechanics — formatter
and linter configuration, invocation, troubleshooting — see
`${CLAUDE_PLUGIN_ROOT}/references/tooling.md`.

Formatting and linting run through Forge: `/phoe:format` and `/phoe:lint`, or the whole
CI-mirror sequence with `/phoe:verify`.

## Crucible Lifecycle Reference

The plugin's Crucible workflows operate on three task types. Match status names exactly — the CLI
rejects unknown statuses (`implementing` and `done` are both invalid), so a wrong status name
causes silent reconciliation failures across `/phoe:implement`, `/phoe:execute`, and
`/phoe:bugfix`.

| Task type | Statuses (in order)                                          | Terminal |
|-----------|--------------------------------------------------------------|----------|
| Challenge | `todo` → `active` → `review` → `merged` (or `blocked`)       | `merged` |
| Bug       | `todo` → `active` → `review` → `merged` (or `blocked`)       | `merged` |
| Saga      | *(no status — tracks collective challenge progress)*         | n/a      |

The full valid set is identical for challenges and bugs: `backlog`, `todo`, `active`, `review`,
`blocked`, `merged`, `canceled`. There is no `implementing` (use `active`) and no `done` (use
`merged`). CLI shape is parallel — `crucible challenge move --label=<L> <status>` /
`crucible bug move --label=<L> <status>`. When writing a workflow that accepts either, branch on
type early and use the type-correct verbs throughout; do not paper over the difference.

Branch naming follows the same split: `challenge/<label>` for challenges, `bug/<label>` for bugs.
Worktrees follow at `.claude/worktrees/<type>-<label>` (slashes converted to dashes).

## Build Commands

Builds go through Forge, never through an external generator — see the repo's forbidden-token
lockdown before reaching for one.

**Worktrees do not share build directories with the main workspace.** Each worktree needs its
own `/phoe:build` run, which configures and builds into that worktree's own profile-suffixed
tree. Do not symlink or reuse the main workspace's build directory from inside a worktree: the
build resolves its project root from where it runs, so a reused tree quietly builds the other
checkout and reports success for code you did not change.

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
  `/phoe:verify` — it drives Forge through audits + build + format + lint + test using the
  active profile, producing the same pass/fail signal as CI. Forge is the only
  way in; the repository's forbidden-token lockdown reds any reach for the
  external generator it replaced.
- When presenting solutions, always ensure the project builds cleanly in Release
  and Headless configurations, and run all appropriate tests beforehand.

## Screenshot Capabilities

For the rule on *how* to capture (and the prohibition on external screenshot apps), see `commands/screenshot.md`. This section documents the underlying engine commands and output paths.

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
Applications/Forge/.forge/<profile>/bin/editor --console-pipe=/tmp/phoenix-console.fifo

# Send commands from another process
echo "aurora.screenshot" > /tmp/phoenix-console.fifo
```

The pipe accepts one command per line. Commands are queued and executed on the main thread each tick.

### Display Requirements

Screenshots require a display server (X11 or Wayland). On headless CI, use `xvfb-run`:

```bash
xvfb-run Applications/Forge/.forge/<profile>/bin/editor --aurora.screenshot.exit
```

## Subagent Definitions

The following agents are available for specialized tasks. Each is defined in `agents/`.

### Core Development
- `invoke-code-reviewer` — C++ code review for bugs, UB, style, portability, and modern C++23 improvements
- `invoke-lint-agent` — clang-tidy static analysis plus include/module-import dependency hygiene

### Architecture & Design
- `invoke-systems-designer` — Cross-platform module architecture and interface design
- `invoke-rendering-designer` — Render graph, material system, and GPU resource architecture
- `invoke-build-engineer` — Forge profiles and manifests, CI/CD, cross-platform builds, toolchains

### Graphics & Rendering
- `invoke-vulkan-agent` — Vulkan API implementation, synchronization, descriptors, and pipelines
- `invoke-shader-expert` — GLSL/SPIR-V compilation, debugging, validation, and optimization

### Platform
- `invoke-platform-agent` — Linux/POSIX and Windows/Win32 platform C++ development and liaison modules

### Testing & Debugging
- `invoke-test-engineer` — Test setup, strategy, coverage, debugging failing tests
- `invoke-debugger-agent` — GDB/LLDB workflows, breakpoints, core dump analysis
- `invoke-memory-agent` — Memory leak detection, ASan/MSan/LSan, Valgrind

### Performance
- `invoke-perf-agent` — CPU profiling, cache analysis, benchmarking, optimization
- `invoke-concurrency-agent` — Thread safety, lock-free algorithms, synchronization

## Reference Documents

The `references/` directory holds the guides an agent consults while working:

- `modern-cpp.md` — C++20/23/26 features, idioms, and migration patterns
- `modern-python.md` — Python 3.12+ features, pathlib, type hints, CLI patterns
- `modern-vulkan.md` — Dynamic rendering, descriptor buffers, synchronization2, timeline semaphores
- `cpp-portability.md` — Cross-platform pitfalls, fixed-width types, alignment, char signedness
- `tooling.md` — Formatter/linter configuration and command reference
- `dispatch-briefs.md` — Dispatch brief format

Phoenix code style is `Docs/StyleGuide.md` in the repository — agent-agnostic, and deliberately
not copied here.

## Permissions

Add new tool permissions to the **user-level** settings (`~/.claude/settings.json`), not the
project-local file (`.claude/settings.local.json`). Project-local permissions override (not merge
with) user-level permissions, so maintaining a separate project allow list causes the user-level
rules to be silently ignored.
