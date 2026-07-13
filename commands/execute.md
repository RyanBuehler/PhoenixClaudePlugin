---
description: Autonomously execute N Crucible challenges via subagents with zero user interaction. Supports parallel execution of independent challenges and sequential execution within sagas.
allowed-tools: Read, Edit, Write, Bash, Glob, Grep, Agent
---

Autonomously execute Crucible challenges using subagents. No user interaction required -- the challenge JSON is the complete spec. Report results at the end.

## Arguments

- **`<N>`** -- execute the next N eligible challenges (saga-aware priority selection)
- **`<saga-label>`** -- execute all remaining todo challenges in a specific saga
- **`next`** -- shorthand for executing the next 1 eligible challenge

Determine which mode by checking if the argument is a number, "next", or a string label.

## 1. Bootstrap

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `build-crucible-release/bin/` and match the expected version. A fresh worktree triggers a one-time clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
build-crucible-release/bin/crucible status
```

Verify workspace is clean:

```bash
git status --porcelain
```

If there are uncommitted changes, stop and tell the user to commit or stash first.

Probe remote reachability before attempting a fetch — sandboxed agent containers often have no SSH agent or credentials and would otherwise fail noisily with `Host key verification failed` / `Could not read from remote repository`:

```bash
if git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
    REMOTE_REACHABLE=1
else
    REMOTE_REACHABLE=0
fi
```

If **reachable** (`REMOTE_REACHABLE=1`), fetch and fast-forward when appropriate:

```bash
git fetch origin main
git log main..origin/main --oneline
```

If there are new commits, fast-forward: `git checkout main && git pull --ff-only origin main`.

If **unreachable** (`REMOTE_REACHABLE=0`), emit a single warning line to the user — e.g., `"origin unreachable, skipping fetch; working from local main"` — and proceed from local main without fetching. Do not abort; do not retry. In autonomous runs the user isn't available to supply credentials, and the work is still valuable against local main.

## 2. Resolve Challenges

**If argument is a number N or "next":**

Use saga-aware priority logic to select N eligible challenges. The candidate pool is the union of saga-attached `todo` challenges and orphan `todo` challenges (challenges that belong to no saga). Both are first-class — orphans have no themed-saga lineage but participate in priority/dependency selection just like saga members.

1. List all sagas: `build-crucible-release/bin/crucible --json saga list`
2. List all todo challenges: `build-crucible-release/bin/crucible --json challenge list --status=todo`
3. Note which of those are orphans for downstream filters: `build-crucible-release/bin/crucible --json challenge list --status=todo --no-saga`. Orphans are challenges with no saga membership; they trivially pass the same-saga ordering check (no predecessors) but still participate in the cross-saga blocker scan and priority selection.
4. Auto-unblock any blocked challenges whose blockers are now merged:
   ```bash
   build-crucible-release/bin/crucible --json challenge list --status=blocked
   ```
   For each, check if the `blocked_by` challenge is now merged. If so: `build-crucible-release/bin/crucible challenge unblock <ID> todo`
5. For each candidate, check saga ordering -- only pick challenges whose saga predecessors are all `merged` or `canceled`. Orphans skip this check (no saga, no predecessors).
6. **Scan for implicit cross-saga blockers (precision-first).** Same-saga ordering only catches explicit dependencies; a challenge may reference a symbol or file from an *unmerged* challenge in a *different* saga via prose. The goal here is to catch the obvious cases (A says "Loads via `Canvas::LoadLayout`" where `Canvas::LoadLayout` is introduced by an unmerged B), **not** to out-smart the implementer. A false-positive skip strands an eligible challenge; a missed implicit blocker becomes one verification failure later — so lean heavily toward letting candidates through. This filter applies to orphans too — they can implicitly block on saga work and vice-versa.

   For each remaining candidate, apply these three filters in order and skip only when **all three** match against the same unmerged challenge:

   **A. Qualified token present.** Extract only qualified tokens from the candidate's `description` / `strategy` / `acceptance_criteria` — `Namespace::Identifier`, `Module.Type`, file paths (`Engine/Modules/Rendering/Mosaic/Canvas.cpp`). Bare PascalCase names (`Config`, `Canvas`, `RenderPass`) are too common; ignore them.

   **B. Unmerged challenge introduces the token.** For each unmerged challenge in any saga, the token must appear in both its prose AND its `affected_files` (i.e., the unmerged challenge is where the symbol is being *introduced* or *modified*, not just mentioned for context). If the token only shows up in the unmerged challenge's prose — as a reference, analogy, or completed API mention — do NOT skip.

   **C. File overlap.** The candidate's `affected_files` must also overlap with the unmerged challenge's `affected_files`. Two challenges that discuss the same symbol but touch disjoint files are not actually coupled.

   Only when A, B, and C all match the same unmerged challenge should the candidate be skipped. Record the skip as: `"blocked by <other-label> (saga #<id> or orphan) via <Token> in <file>"`. Do not auto-mark as blocked in Crucible — this is a scheduling hint, not a state change, and the user may judge the dependency is stale. Include the full skip reason in the final report so the user can override if the heuristic was wrong.
7. Among the candidates that pass both explicit and implicit blocker checks, pick by: priority (critical > high > medium > low), then lowest ID.
8. Repeat until N challenges are selected. Skip challenges that would be blocked by other challenges in the candidate list.

Report skipped candidates (both the implicit-blocker reason and priority/wave-already-full reasons) in the final execute summary so the user can see the selection trail.

**If argument is a saga label:**

```bash
build-crucible-release/bin/crucible --json saga show --label=<SAGA_LABEL>
```

Collect all todo challenges in saga order. These will be executed sequentially. Saga-scoped mode is explicitly bounded — orphans are NOT included even when otherwise eligible.

If no eligible challenges exist, report this and stop.

## 3. Classify Parallelism

Build a dependency graph among the resolved challenges:

- **Same-saga edge:** If challenges A and B are in the same saga and A has a lower position, A must complete before B.
- **File-overlap edge:** If challenges A and B have overlapping `affected_files`, the lower-ID challenge goes first.

Partition into execution **waves** via topological levels:
- **Wave 0:** All challenges with no incoming dependency edges (can run in parallel).
- **Wave 1:** Challenges whose only predecessors are in wave 0.
- Continue until all challenges are assigned.

Print the execution plan:

```
Execution Plan:
  Wave 0 (parallel): #42 add-viewport-resize, #54 forge-compiler-launcher
  Wave 1 (sequential): #43 wire-canvas-events (depends on #42)
```

## 4. Execute Waves

For each wave, execute the following steps:

### Docs-only fast path

Classify each challenge before running its steps. A challenge is **docs-only** when its
`affected_files` and acceptance criteria touch no C++, build, or test code -- the deliverable is
a design document, spec, or other Markdown/prose artifact. Everything else is a **code**
challenge and runs the full 4a-4h cycle below unchanged.

The full 4d/4e/4f cycle is calibrated for code, where CRITICAL means "may crash production". For
a design doc, CRITICAL means "this number is wrong" or "this assumes infrastructure that does not
exist" -- both reviewable on the PR rather than requiring a second verification pass. So docs-only
challenges diverge as follows (step numbers still map to 4a-4h):

- **No build, no `/phoe:verify`.** Skip `/phoe:build` and `/phoe:verify` -- there is nothing to
  compile or test. Drop steps 1 (populate build dir) and 6 (run `/phoe:verify`) from the
  implementer subagent prompt and tell it the change is prose-only.
- **4d becomes a prose-ground check.** In place of build+verify, scan the draft for grounding
  defects: path references that do not resolve (`Engine/<X>/`, `Project/<X>/`, nonexistent
  helpers / toolchains / inspector pages -- see the Grounding constraint) and determinism claims
  with no stated posture. Fix what you find before review.
- **Single-round review (4e/4f).** Run ONE adversarial review pass and ONE fix pass, then advance
  to PR. The fix pass must resolve every CRITICAL and WARNING (WARNING is a blocking tier here too);
  log only suggestions/notes and advance. Re-enter a second review+fix round ONLY if the first-round
  CRITICAL count is >= 3. The spec and quality reviewers remain optional adds; the adversarial pass
  plus the grounding check is the gate.
- **Suppress task-tool reminders in the subagent.** Tell the docs-only implementer subagent to
  ignore any "task tools haven't been used recently" harness reminders -- the orchestrator owns
  wave-level task tracking, and a single-file design doc does not benefit from a local task list.

### 4a. Setup

Worktrees are mandatory for every challenge — the plugin's `branch-worktree-check.py` hook blocks bare `git checkout -b` / `git switch -c` / `git branch <name>` at tool-use time (by design, to enforce one-worktree-per-branch). `git worktree add -b <name>` is the only supported way to create a challenge branch.

Every worktree is an independent checkout with its own build dir. CMake caches absolute source paths per checkout, so each worktree pays a first-time build (~3–4 min). That cost is inherent to the isolation, not avoidable by branching on main — so the implementer subagent runs `/phoe:build` as its first concrete action (see 4b, step 5 of the subagent prompt).

#### Branch strategy decision (per wave)

Before creating worktrees, decide how challenges in the wave map onto branches. Two patterns:

- **Branch-per-challenge** (default for parallel work) — every challenge gets its own
  `challenge/<label>` branch and worktree. Required when challenges in the wave can run in
  parallel (no dependency edges between them) — they need isolated checkouts to run
  simultaneously without colliding. Each challenge ends up as its own PR.
- **Combined branch** (for short, dependent runs) — multiple consecutive challenges share one
  branch and one worktree. Only valid when the challenges form a strict dependency chain (each
  must run after the previous), are intended to ship together, and total ≤4 challenges.
  Long chains are still better as branch-per-challenge so an early failure does not block the
  whole batch.

Apply this rule to each wave:

1. If the wave has more than one challenge that can run in parallel (i.e. the wave is parallel
   by construction), use **branch-per-challenge** for every challenge in the wave. Combining is
   not an option for parallel work.
2. If the wave is a single challenge whose predecessor was the prior wave's only challenge
   *and* both belong to the same saga *and* the prior challenge has not yet been merged to
   `main`, prefer **combined branch** — extend the prior challenge's branch in the same
   worktree rather than branching from main. The combined branch is named after the saga (e.g.
   `challenge/saga-<saga-label>`) so its identity does not depend on any single challenge label.
3. Cap any combined branch at 4 challenges. After 4, start a fresh branch for the next chunk.

Record the chosen strategy per challenge — it determines whether each challenge becomes its
own PR or whether the wave shares a single combined PR (see step 4g). Do not change strategy
mid-wave.

For each challenge in the wave:

1. Read the full challenge JSON (run from the main repo root):
   ```bash
   build-crucible-release/bin/crucible --json challenge show --label=<LABEL>
   ```
2. Re-confirm status is still `todo` (parse from the JSON above). Another agent's parallel
   `/phoe:execute` may have claimed it since Step 2. If status is anything else, drop the
   challenge, log "Pre-empted by parallel agent" in the final report, and continue.
3. Create the worktree and branch from the main repo root, basing it on the right ref so the PR
   diff is clean and dependencies are visible without ever writing local `main`:
   - **Default:** base on `origin/main` when the remote is reachable (`REMOTE_REACHABLE=1` from
     Step 1), else local `main`.
   - **Stacked dependency:** if this challenge depends on an earlier challenge *in this run* whose
     work is not yet on `origin/main` -- a cross-wave dependency that is not already on a shared
     combined branch -- base it on that predecessor's branch tip (`challenge/<predecessor-label>`)
     instead, so the dependency is present locally without merging anything into `main`.
   ```bash
   git worktree add .claude/worktrees/challenge-<label> -b challenge/<label> <base-ref>
   ```
   where `<base-ref>` is `origin/main`, `main`, or `challenge/<predecessor-label>` per the rule above.
4. Move to active (run from the main repo root so the crucible binary resolves):
   ```bash
   build-crucible-release/bin/crucible challenge move --label=<LABEL> active
   ```

For challenges using the **combined branch** strategy (per the rule above), do NOT create a
new worktree — reuse the existing combined worktree. Skip the `git worktree add` step and
instead `cd` into the existing worktree. Move the challenge to `active` as normal.

Each fresh worktree is an independent checkout; local `main` is never written by `/phoe:execute` —
all work stays on the challenge branch through 4h (see 4d).

**Parallel-build caching note (bug 8 follow-on).** When a wave has multiple challenges running in parallel, each worktree does a cold build. Configuring ccache project-wide so shared objects are cache hits (~30s vs ~4min rebuild) is a separate optimization tracked outside this command — not part of /phoe:execute's responsibility. See CLAUDE.md "Build Commands" for the worktree build constraint.

### 4b. Implement (parallel within wave)

Dispatch one implementer subagent per challenge; each works in the worktree pre-created for it in
4a. Its prompt's Step 1 commands run there.

**The Agent tool has no `cwd` parameter** — a subagent inherits the orchestrator's working
directory. To place an implementer in its worktree, the orchestrator calls
`EnterWorktree(path=".claude/worktrees/challenge-<label>")` (combined branch: the shared worktree)
*before* dispatching, so the subagent inherits that cwd.

**Background-session write-guard.** When `/phoe:execute` runs as a background session, Claude
Code's isolation guard rejects `Write`/`Edit` in any worktree the parent session has not isolated
into ("parent bg session hasn't isolated yet") — the implementer can `cd` and build via Bash but
cannot use the native file tools. The `EnterWorktree(path=...)` above also satisfies this guard,
so do it before dispatching the wave's first implementer. If a subagent still reports it cannot
Write/Edit, tell it (in the prompt) to author files via Bash — single-quoted heredocs for new
files, `python` exact-string replace with an `assert count == 1` for edits — which the guard does
not intercept.

**Never pass `isolation: "worktree"` to implementer subagents.** The branch and worktree already
exist (4a); `isolation: "worktree"` spawns a *fresh, auto-named* worktree off `main`, so the
subagent ignores the prepared `challenge/<label>` branch and, on stacked/combined work, abandons
its accumulated commits. Use the default **general-purpose** agent. (The specialist `phoe:invoke-*`
agents carry `isolation: worktree` intrinsically and self-isolate off `main` — don't use them for
stacked implementer work; if one was, recover the commit by fast-forwarding its `agent-<hash>`
branch.)

For a parallel wave of independent worktrees, enter-and-dispatch one worktree at a time (the
orchestrator occupies a single cwd); within each, the implementer addresses files by absolute
worktree path. Combining is never used for parallel work (4a), so each parallel implementer is its
own dispatch.

**Implementer subagent prompt template:**

Construct the prompt with ALL of these sections -- the subagent has no conversation context:

```
You are autonomously implementing a Crucible challenge for the Phoenix engine.
Work directly -- no user interaction. If you get stuck, report BLOCKED.

## Challenge
Title: <title>
Label: <label>
Description: <description>

## Strategy
<strategy items, numbered -- or "No strategy provided, use your judgment based on the codebase">

## Acceptance Criteria
<numbered acceptance criteria>

## Verification Commands
<verification steps with commands>

## Affected Files
<list of files expected to be modified>

## Saga Context
<if applicable: saga name, this challenge's position, what prior challenges accomplished>

## Project Conventions
<paste relevant CLAUDE.md sections -- especially coding standards, naming conventions, build system>

## Your Job

1. **Populate the worktree's build dir (FOREGROUND).** Your `cwd` is a fresh git worktree with no `build-editor-*/` directory yet. Build once as your first action — Forge configures and builds via the active profile. Run the build in the **foreground** and wait for it to finish in this same turn; do NOT launch it in the background and yield your turn waiting for a completion notification — that strands you with edits unverified and uncommitted. If a build helper would background itself, run the underlying build command directly in the foreground. Do this before exploring: you'll want the compilation database present so `grep`/`Read`-based exploration works correctly on modules that use C++23 modules, and so your later `/phoe:verify` run is an incremental build, not a cold one.
2. Read the affected files and explore related Phoenix code to understand the context. **Ground your approach in Phoenix's own patterns** — if the challenge touches UI, read Mosaic/Tessera/Emblema code; if it touches input, read Impulse; if it touches the renderer, read Aurora/Prism/Vulkan code. Do NOT generalize from external frameworks (ImGui, Qt, React, etc.) or from memory of how similar problems are solved elsewhere — that frequently ships wrong assumptions into the diff. When in doubt, grep for analogous existing features and mirror their shape.
3. Follow the strategy steps (if provided) or plan your own approach based on what you read in step 2
4. Implement the changes
5. Write tests if your implementation introduces new public interfaces or non-trivial logic
   - Tests are NOT needed for: build system changes, config changes, pure wiring/delegation
6. Run `/phoe:verify` — this runs build, format, lint, and test through Forge with the project's
   configured profile. Fix any failures before proceeding. Do NOT invoke cmake/ctest directly;
   `/phoe:verify` is the single entry point for verification.
7. Run the challenge's own Verification Commands (from the section above). These are scoped to
   this specific challenge and complement the project-wide `/phoe:verify` sweep. Fix any failures.
8. Self-review against each acceptance criterion
9. Commit your changes with a descriptive message referencing the challenge label
10. Report back

## Constraints
- Do NOT enter plan mode
- Do NOT ask the user questions -- if you need information, read the codebase
- Do NOT modify files outside the challenge's scope unless absolutely necessary
- **Grounding -- cite only what exists.** Before referencing any project helper, type,
  toolchain, tool, inspector page, script, vendored dependency, or directory -- in code,
  comments, commit messages, or design-doc prose -- confirm it exists with `grep` / `Glob` /
  `Read`. If the search returns nothing, do NOT assert it exists: drop the reference, or (in a
  design doc) mark it explicitly as an **Upstream Dependency** still to be built. This is the
  inverse of CLAUDE.md "Search before claiming the codebase lacks something" -- the same
  discipline applies to claiming something *does* exist. Phoenix's tools live at the top-level
  `Tools/`, NOT `Engine/Tools/`; there is no `Engine/Tools/` directory. Treat any
  `Engine/<X>/`, `Project/<X>/`, or similar path as suspect until a `Read`/`Glob` confirms it.
- **Determinism claims need a stated posture.** Any "bit-exact", "deterministic", or
  "reproducible" claim must cite the explicit conditions that make it true: BLAS thread counts
  (`OPENBLAS_NUM_THREADS=1` / `MKL_NUM_THREADS=1`), pinned library versions, seeded RNG. If you
  cannot state the posture, downgrade the wording to "deterministic under <posture>" or
  "best-effort reproducible". Bit-exact across BLAS-threaded numerics or an unpinned
  compression library is false by default, even on a single host.
- Follow the project's coding conventions (CLAUDE.md) — **and before writing any C++, read `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` and `${CLAUDE_PLUGIN_ROOT}/references/tooling.md`** so the implementation conforms to enforced conventions (formatting, naming, comments, namespaces, return-value handling, `auto`, scope spacing, tooling). `${CLAUDE_PLUGIN_ROOT}` is the plugin install path — `cat` these via Bash so the shell expands the variable; if it is unset, use `~/phoenixclaudeplugin/references/`
- Use plain ASCII only -- no unicode characters
- **Do not yield your turn until committed + reported.** Run builds and tests in the FOREGROUND; ending your turn with edits unverified or uncommitted (e.g. waiting on a backgrounded build) strands the work and the orchestrator cannot resume you mid-task.
- **Use worktree-absolute paths.** The paths in your prompt/context use the main-repo form (`/home/ryan/phoenix/...`), but the files you must edit live under the worktree prefix (`.claude/worktrees/challenge-<label>/...`). Reading the main-repo path can serve stale content, and a later `Edit` then fails "File has not been read yet" — read and edit the worktree copy.
- **This shell is zsh.** Quote `grep --include` globs (`'*.cpp'`, not `*.cpp`) and do not rely on unquoted `$VAR` word-splitting — pass file lists literally or use arrays. An unquoted multi-file variable collapses to a single argument and silently checks nothing.
- **Numeric safety.** Any clamp / `min` / `max` over a caller-supplied float must guard with `isfinite`/`isnan` FIRST — `std::clamp`/`min`/`max` pass NaN straight through into casts and persisted state. This is a recurring CRITICAL class the adversarial reviewer keeps catching.
- **Byte/format-parser safety.** Bound every allocation and element count by the actual payload/blob size BEFORE any `reserve`/`resize`/multiply; a hostile count field otherwise drives a multi-GB reserve or a `length_error`/terminate (Phoenix bans exceptions). Add an adversarial regression trial with inflated counts — the happy-path round-trip cannot catch this.
- Use full descriptive variable names -- no abbreviations
- Prefer sized integer types (int32_t, uint64_t) over platform-dependent types
- Comments: default to none. Prefer one line; two or three for the genuinely complex. *Why*, not *what*. Paragraphs belong in the commit message. Full rules in `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` §Comments.
- TODO comments must follow the discipline in the plugin's CLAUDE.md "TODO Comments" section:
  short, describe the work itself, never reference anything that can go stale (file paths, line
  numbers, challenge labels, PR numbers, branch names, dates), and never narrate refactors you
  just made. If a TODO needs more than one line, file it as a Crucible challenge instead.

## Workflow Friction Log
At the end of your report, include a "## Workflow Friction" section listing any issues
you encountered that slowed you down or required workarounds:
- Command errors or unexpected tool behavior
- Missing or unclear context in the challenge spec
- Codebase patterns that were hard to discover
- Files that were harder to find than expected
- Permission issues or sandbox limitations
- **Context bloat** -- tools or defaults that flooded your context window with low-signal output.
  Call these out specifically so they can be tuned. Examples:
  - CMake configure/build emitting hundreds or thousands of lines of trace/debug output when
    only pass/fail + errors are needed
  - The engine running with verbose trace logging on by default, producing a wall of breadcrumbs
    on every launch (Scribe traces, Vulkan validation spam, asset loader chatter, etc.)
  - Test runners printing full per-test logs instead of a summary on success
  - `ctest`, `ninja`, or other tools defaulting to verbose mode and burying the actual failure
  - Any tool whose default output is so noisy that you had to grep/head/tail it to stay useful
  When you flag a context-bloat item, name the specific tool/flag/subsystem so the fix is
  actionable (e.g. "CMake `--log-level=VERBOSE` is on by default in the Forge wrapper" rather
  than "build output was noisy").
- Anything that would help future autonomous runs go smoother

## Report Format

Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
What was implemented: (summary)
Tests added: (list or "N/A")
Files changed: (list)
Self-review: (per-criterion pass/fail)
Concerns: (if DONE_WITH_CONCERNS)
Blocker: (if BLOCKED -- what specifically is preventing progress)
Questions: (if NEEDS_CONTEXT -- what specific information is needed)

## Workflow Friction
(list issues encountered)
```

### 4c. Handle Implementer Results

For each returning subagent:

| Status | Action |
|--------|--------|
| **DONE** | Proceed to 4d (Rebase + Verify) |
| **DONE_WITH_CONCERNS** | Read concerns. If about correctness/scope: dispatch a targeted fix subagent. If observational: note and proceed. |
| **BLOCKED** | Retry once: re-read the affected files and any files the subagent mentioned, enrich the prompt with additional context from the codebase, and re-dispatch. On second BLOCKED: mark challenge blocked in Crucible with detailed explanation, write checkpoint to `.claude/handoffs/<LABEL>-checkpoint.md`, **keep the branch and commits intact**. Skip to next challenge. |
| **NEEDS_CONTEXT** | Retry once: read the subagent's questions, answer them by reading the codebase/CLAUDE.md/sibling saga challenges, and re-dispatch with enriched context. On second NEEDS_CONTEXT: mark blocked with unanswered questions as the reason, **keep the branch intact**. Skip. |

When marking a challenge blocked:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> blocked
```

Write a checkpoint file:

```markdown
# Checkpoint: <LABEL>
## Challenge
<title and description>
## What Was Attempted
<summary of subagent's work>
## Why It Failed
<specific failure reason from subagent report>
## Suggested Next Steps
<concrete steps for human to continue>
## Subagent Report
<full subagent report for context>
```

### 4d. Rebase + Verify (sequential, per challenge in ID order)

All post-implement work stays on the challenge branch in its own worktree. **Local `main` is never
checked out, merged into, or committed to by `/phoe:execute`.** When more than one agent is active,
local `main` is shared mutable state — writing to it bundles unrelated parallel commits into the
PR (and the old "merge to main, fix on main, push the branch" flow silently left those fixes off
the pushed branch entirely). The PR *is* the challenge branch; `main` only moves when a PR merges
on the remote.

For each completed challenge, working inside its worktree (`.claude/worktrees/challenge-<label>`):

1. Rebase the branch onto the freshest upstream so the PR diff is minimal. When the remote is
   reachable (`REMOTE_REACHABLE=1` from Step 1):
   ```bash
   git -C .claude/worktrees/challenge-<label> fetch origin main
   git -C .claude/worktrees/challenge-<label> rebase origin/main
   ```
   When unreachable, skip the fetch and `git -C <worktree> rebase main` onto local `main`.
   Combined-branch chains rebase the shared branch once, not once per challenge.

2. If the rebase conflicts: `git -C <worktree> rebase --abort`. Mark the challenge blocked with
   "Rebase conflict with origin/main on files: <list>". **Keep the branch intact.** Skip.

3. Run full project verification via `/phoe:verify` from inside the worktree. Forge drives the full
   sequence: configure + build, format check, lint (clang-tidy on changed files), and test.

4. Run challenge-specific verification commands from the challenge JSON.

5. On verify failure: dispatch a fix subagent (cwd = the worktree) with the error output; it commits
   the fix to the challenge branch. Re-run `/phoe:verify`. On second failure: mark blocked with the
   verify error output. **Keep the branch and its commits intact.** Skip.

### 4e. Review (spec + quality + adversarial in parallel per challenge)

Process challenges in ID order. For each challenge, dispatch all three reviewers simultaneously (they are read-only, so parallel dispatch is safe), wait for all to return, then move to the next challenge. Reviewers diff the challenge branch against its upstream base with three-dot range `origin/main...HEAD` (use `main...HEAD` when origin is unreachable) — this captures the full PR diff regardless of how many commits the branch carries, and never depends on local `main`.

**A reviewer that returns with zero tool uses and no verdict is a failed dispatch, not a pass.** Reviewers occasionally terminate early (no `git diff` run, no per-criterion table). Detect this — an empty or verdict-less return — and re-dispatch that reviewer once with the same prompt; never treat an empty review as a clean gate.

The adversarial reviewer is a **mandatory pre-PR gate** — no challenge advances to 4h without it. The standard quality reviewer asks "is this code well-formed?"; the adversarial reviewer asks "how does this break?". Both are required because they catch different failure modes, and `/phoe:execute` ships PRs without human judgment in the loop, so the adversarial pass is the last line of defense before the diff lands on `origin`.

For each verified challenge:

**Spec reviewer** -- launch `invoke-spec-reviewer` agent:

```
Review spec compliance for challenge: <label>

## Acceptance Criteria
<numbered criteria from challenge JSON>

## Strategy
<strategy from challenge JSON, if present>

## Diff
Run: git diff origin/main...HEAD (use main...HEAD if origin is unreachable)

## Files Changed
<list from git diff --name-only origin/main...HEAD>
```

**Quality reviewer** -- launch `invoke-code-reviewer` agent:

```
Review the branch diff (git diff origin/main...HEAD; use main...HEAD if
origin is unreachable) for challenge branch.
Focus on correctness, safety, modern C++23 opportunities, performance,
and project convention compliance. Report findings using
CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
```

**Adversarial reviewer** -- launch a second `invoke-code-reviewer` agent (fresh, no shared context with the quality reviewer) with this prompt:

```
Adversarially review the diff (git diff origin/main...HEAD; use main...HEAD
if origin is unreachable) for challenge: <label>.
Your job is to attack this implementation, not validate it. Assume the
quality review is happening in parallel — do not duplicate it. Hunt for:

- Edge cases the implementation does not handle (empty input, max-size
  input, unicode, negative values, NaN, integer overflow, signed/unsigned
  mismatches, off-by-one at boundaries).
- Concurrency hazards: races, reentrancy, ordering assumptions across
  threads or subsystems, lifetime invariants not enforced by the type
  system.
- Silent failure modes: paths that swallow errors, no-op on the
  unexpected branch, or fail to log via Scribe.
- Hidden coupling: state shared across modules, ownership confusion,
  assumptions about call order or initialization sequence.
- Performance pathologies under realistic load (allocation in hot paths,
  O(n²) under expected n, lock contention, cache-hostile patterns).
- Spec gaps: acceptance criteria that pass for the easy case but fail in
  plausible variations the spec did not enumerate.

Report only findings that represent real failure modes, not stylistic
concerns. Use CRITICAL/WARNING/SUGGESTION/NOTE severity. If you find
nothing actionable, say so explicitly — a clean adversarial pass is a
valid result.
```

### 4f. Handle Review Results

**Where fixes land.** Every fix and triage subagent in this step commits to the **challenge
branch in its own worktree** (cwd = `.claude/worktrees/challenge-<label>`) — never to local
`main`, preserving the "no direct commits to main" rule. Because each challenge owns an isolated
worktree, per-challenge fix subagents do not collide; but run multiple fix/triage passes for the
*same* challenge sequentially (each must finish — commits landed, verify passed — before the next
starts) so a later pass sees the earlier one's committed state.

If a fix would materially change the shape of the work rather than touch it up, mark the challenge
blocked instead and let the user re-plan.

Process challenges in **ID order** within the wave, and for each one:

- **Spec FAIL, quality CRITICAL or WARNING, or adversarial CRITICAL or WARNING:** Dispatch a fix subagent with combined feedback from every reviewer that flagged a blocker (spec, quality, adversarial — whichever fired). Wait for it to finish. Re-run `/phoe:verify`. Re-dispatch **all three** reviewers (a fix can introduce new adversarial-class regressions). On second failure: mark blocked with reviewer feedback. **Keep all branches and commits intact.** Skip this challenge and move to the next one in the wave. WARNING is a blocking tier alongside CRITICAL — an autonomous run has no human to waive one, so an unresolved WARNING blocks the challenge for human review rather than shipping with it ignored.
- **Quality SUGGESTION or adversarial SUGGESTION:** Dispatch a suggestion-triage subagent with the combined suggestion list (both sources merged, deduplicated). For each suggestion the subagent must decide:
  - **Implement it** if it is clearly in-scope, correct, and adds value -- apply the change directly.
  - **Defer it** if it raises a real question, is ambiguous, or is out of scope for this challenge -- emplace a `// TODO: <one-line description of the work that needs doing>` comment at the most relevant code location so it can be evaluated later. Follow the TODO discipline in the plugin's CLAUDE.md: describe the work, not where the note came from; never embed the challenge label, a PR number, a file path, a line number, a branch name, or any other reference that can go stale.

  Suggestions must never be silently dropped. The triage subagent commits any changes (implementations and TODOs) to the challenge branch in its worktree. Wait for it to finish. After it returns, re-run `/phoe:verify`. Do NOT re-dispatch the reviewers. Log the triage outcome (implemented / deferred counts, broken out by source) in the final report.
- **Quality NOTE or adversarial NOTE:** Proceed. Log notes in the final report.

A challenge cannot reach 4h (Publish) until all three reviewers have returned and zero CRITICAL and zero WARNING findings remain across spec, quality, and adversarial. The adversarial gate is non-skippable — autonomous PR submission without it is forbidden.

### 4g. Move to Review

For each successfully reviewed challenge:

1. Move to review: `build-crucible-release/bin/crucible challenge move --label=<LABEL> review`
2. **Reconcile follow-on siblings and docs** (pre-merge pass) -- this implementation may have invalidated later sibling specs *or* `docs/` design/spec files: a rename or API change leaving a sibling's `description`, `strategy`, `affected_files`, or `acceptance_criteria`, or a doc, referring to the old name. Do a best-effort pass now against the committed diff; the authoritative pass runs post-merge in Step 6.
   1. `build-crucible-release/bin/crucible --json saga show --label=<SAGA_LABEL>` lists remaining todo + blocked siblings after this challenge's position. (Skip for orphans -- no siblings -- but still run the docs scan below.)
   2. Scan each later sibling's text (`build-crucible-release/bin/crucible --json challenge show --label=<SIBLING_LABEL>`) **and** `docs/` design/spec files against the committed diff for stale references: renamed types / functions / files, changed signatures, moved modules, replaced concepts.
   3. Fix each surgically -- `build-crucible-release/bin/crucible challenge update --label=<SIBLING_LABEL> [--field=...]` (run `--help` for flags) for sibling text; an in-place edit on this challenge's branch (rides the same PR) for docs. Update only stale references; do not rewrite scope.
   4. Record sibling + doc updates for the final report (which siblings/docs, which fields). If a later sibling's scope is genuinely broken (not just a rename), do not rewrite it -- flag it as a blocked-follow-on in the report and let the user re-plan.

**Blocked challenge policy:** Never revert branches or discard commits from blocked challenges. Partial work is valuable context for human resumption via `/phoe:implement <label>`. Always keep branches, commits, and checkpoint files intact.

### 4h. Publish

**Pre-push race check.** Before pushing, re-fetch and check origin/main for equivalent work — a
parallel agent may have landed a similar PR. Otherwise the rebase drops your commits as
cherry-pick-equivalent and leaves an empty PR.

```bash
git fetch origin main
git log origin/main --oneline -i --grep="<label>" -10
```

If no match, rebase the branch once more onto the freshest origin/main so the push is a clean
fast-forward of the PR head (origin/main may have advanced since 4d):

```bash
git -C .claude/worktrees/challenge-<label> rebase origin/main
```

If this rebase conflicts, abort it, mark the challenge blocked with the conflicting files, keep
the branch intact, and skip.

If matches exist, mark merged, clean up the branch/worktree, log "Pre-empted by parallel agent"
in the final report, and skip to the next challenge:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> merged
git worktree remove .claude/worktrees/challenge-<label>  # branch-per-challenge only
git branch -D challenge/<label>
```

For every reviewed challenge that survives the pre-push check, push its branch and open a pull
request. Group by strategy:

- **branch-per-challenge:** push the challenge branch and create a single-challenge PR.
- **combined-branch:** wait until every challenge in the chain has reached `review`, then push
  the shared branch once and create one PR that lists all the challenges it carries.

```bash
# branch-per-challenge
git push -u origin challenge/<label>
PR_URL=$(gh pr create \
  --head challenge/<label> \
  --base main \
  --title "<challenge title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullets describing what the branch accomplishes>

Crucible: #<id> <label>
Saga: #<saga-id> <saga-label>
EOF
)")
PR_NUM="${PR_URL##*/}"
echo "Opened PR #${PR_NUM}: ${PR_URL}"
build-crucible-release/bin/crucible challenge update --label=<LABEL> --replace-review-link="${PR_URL}"
```

```bash
# combined-branch
git push -u origin challenge/saga-<saga-label>
PR_URL=$(gh pr create \
  --head challenge/saga-<saga-label> \
  --base main \
  --title "<saga title>" \
  --body "$(cat <<'EOF'
## Summary
<bullets covering all challenges in the chain>

Crucible: #<id-1> <label-1>, #<id-2> <label-2>, #<id-3> <label-3>
Saga: #<saga-id> <saga-label>
EOF
)")
PR_NUM="${PR_URL##*/}"
echo "Opened PR #${PR_NUM}: ${PR_URL}"
# Combined PR covers every challenge in the chain — record the same review link on each one
# so subsequent `crucible challenge show` calls all surface the PR URL.
for LBL in <label-1> <label-2> <label-3>; do
  build-crucible-release/bin/crucible challenge update --label="${LBL}" --replace-review-link="${PR_URL}"
done
```

`Crucible:` and `Saga:` trailers are mandatory; pull IDs from the JSON already fetched in Step 2. Combined-branch PRs list every challenge in the chain. Drop the `Saga:` line for orphans.

The `--replace-review-link` step after each `gh pr create` is source-neutral by design — the
flag accepts any URL string, so a non-GitHub review system fits without rewording this step.

Refer to each PR as **PR #<N>** (the trailing `/pull/<N>` segment) in narration, the Report table, and the Watch CI step — never URL alone. Record each `PR #<N>` + URL for the final report.

After the wave's PRs are open, clean up worktrees (the branches and commits stay until the
user removes them):

- **branch-per-challenge:** `git worktree remove .claude/worktrees/challenge-<label>` after
  pushing.
- **combined-branch:** only remove the shared worktree after the chain's PR has been pushed.

If a PR comment loop later requests fixes, check out the branch, apply the change, rebuild
(full `/phoe:verify` only when changes are significant), commit with a brief
"Address review: …" message, and push.

## 5. Subagent Feedback Log

After all waves complete, collect the "Workflow Friction" sections from every subagent report and append them to `.claude/SUBAGENT_FEEDBACK.md`:

```markdown
## <date> - /phoe:execute <args>

### Challenge: <label> (implementer)
- <friction item 1>
- <friction item 2>

### Challenge: <label> (spec-reviewer)
- <friction item>

### Challenge: <label> (quality-reviewer)
- <friction item>

### Challenge: <label> (adversarial-reviewer)
- <friction item>
```

This feedback file helps the user evolve CLAUDE.md, challenge specs, and the plugin to be more conducive for autonomous operation.

## 6. Report

Print a summary table:

```
/phoe:execute Results
=====================

| Challenge | Wave | Status | Branch | PR | Notes |
|-----------|------|--------|--------|----|-------|
| add-viewport-resize | 0 | review | challenge/add-viewport-resize | #1234 | -- |
| forge-compiler | 0 | blocked | challenge/forge-compiler | -- | Build failure: missing include |
| wire-canvas-events | 1 | review | challenge/wire-canvas-events | #1235 | Fixed 1 WARNING (large function) before review |

Saga Progress:
  synthetic-input: 3/6 complete (was 2/6)
  (orphan): 1 challenge processed this run

Blocked Challenges:
  forge-compiler: Build failure in ForgeCompiler.cpp:42 -- missing include for <filesystem>.
  Checkpoint written to .claude/handoffs/forge-compiler-checkpoint.md
  Resume with: /phoe:implement forge-compiler

Stats: 2 completed, 1 blocked, 0 skipped
Feedback logged to: .claude/SUBAGENT_FEEDBACK.md
```

Include:
- Saga progress updates for all affected sagas
- Reconciliation outcome (pre-merge pass, Step 4g.2): siblings + `docs/` scanned against each committed diff -- which siblings/docs were updated, any flagged-as-broken follow-ons that need user re-planning, or "none stale" (required -- a present line makes a skipped reconciliation visible). The authoritative post-merge pass runs later when each PR lands and reports its own outcome then.
- Full explanation for each blocked challenge
- Reference to checkpoint files and how to resume
- Total stats (completed, blocked, skipped)
- Branch strategy per challenge (branch-per-challenge or combined-branch) and resulting **PR #<N>** + URL. Lead with `PR #<N>`.
- CI watch outcome per PR: READY / FAILED / expired / skipped (reason)
- Reference to the feedback log

After each PR lands on remote main, mark the corresponding challenge merged, then run the **end-of-cycle reconciliation** (the authoritative pass) against its merged diff. This fires whenever the merge is observed -- e.g. the next `/phoe:execute` Step 2, or interactively -- not inside the run that opened the PR:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> merged
```

Re-scan the merged diff against every remaining todo/blocked challenge (saga sibling or orphan) **and** `docs/` design/spec files for stale references the pre-merge pass (Step 4g.2) missed or that only the landed diff made certain. Fix challenge text in place with `crucible challenge update`. For stale docs, file a tracked docs-reconcile challenge (`/phoe:plan`) so the edit flows through the normal implement + CI-watch path rather than an untracked side PR -- the original challenge branch is gone post-merge. Flag genuinely scope-broken siblings as blocked for re-plan rather than rewriting them. Report this pass's outcome when it runs.

## 7. Watch CI — Required

Run the collective watch loop in `references/ci-watch.md` against every `PR #<N>` opened in Step 4h. Mandatory; skip only on the conditions listed in `ci-watch.md`. It babysits each PR's CI to a terminal green or red, making **one** automated fix-and-retry per PR on its first failure before leaving it red for the user. Fold each PR's outcome (READY / FAILED / expired / skipped) into the Step 6 report.
