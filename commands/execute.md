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

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `build-crucible-${PHOE_ENV}-release/bin/` and match the expected version. A fresh worktree, or a first-time switch between host and container environments, will trigger a one-time clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

Resolve the environment suffix for subsequent invocations (include this line at the top of every bash block that touches a binary):

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
```

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible status
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

Use saga-aware priority logic to select N eligible challenges:

1. List all sagas: `build-crucible-${PHOE_ENV}-release/bin/crucible --json saga list`
2. List all todo challenges: `build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge list --status=todo`
3. Auto-unblock any blocked challenges whose blockers are now merged:
   ```bash
   build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge list --status=blocked
   ```
   For each, check if the `blocked_by` challenge is now merged. If so: `build-crucible-${PHOE_ENV}-release/bin/crucible challenge unblock <ID> todo`
4. For each candidate, check saga ordering -- only pick challenges whose saga predecessors are all `merged` or `canceled`.
5. **Scan for implicit cross-saga blockers (precision-first).** Same-saga ordering only catches explicit dependencies; a challenge may reference a symbol or file from an *unmerged* challenge in a *different* saga via prose. The goal here is to catch the obvious cases (A says "Loads via `Canvas::LoadLayout`" where `Canvas::LoadLayout` is introduced by an unmerged B), **not** to out-smart the implementer. A false-positive skip strands an eligible challenge; a missed implicit blocker becomes one verification failure later — so lean heavily toward letting candidates through.

   For each remaining candidate, apply these three filters in order and skip only when **all three** match against the same unmerged challenge:

   **A. Qualified token present.** Extract only qualified tokens from the candidate's `description` / `strategy` / `acceptance_criteria` — `Namespace::Identifier`, `Module.Type`, file paths (`Modules/Mosaic/Canvas.cpp`). Bare PascalCase names (`Config`, `Canvas`, `RenderPass`) are too common; ignore them.

   **B. Unmerged challenge introduces the token.** For each unmerged challenge in any saga, the token must appear in both its prose AND its `affected_files` (i.e., the unmerged challenge is where the symbol is being *introduced* or *modified*, not just mentioned for context). If the token only shows up in the unmerged challenge's prose — as a reference, analogy, or completed API mention — do NOT skip.

   **C. File overlap.** The candidate's `affected_files` must also overlap with the unmerged challenge's `affected_files`. Two challenges that discuss the same symbol but touch disjoint files are not actually coupled.

   Only when A, B, and C all match the same unmerged challenge should the candidate be skipped. Record the skip as: `"blocked by <other-label> (saga #<id>) via <Token> in <file>"`. Do not auto-mark as blocked in Crucible — this is a scheduling hint, not a state change, and the user may judge the dependency is stale. Include the full skip reason in the final report so the user can override if the heuristic was wrong.
6. Among the candidates that pass both explicit and implicit blocker checks, pick by: priority (critical > high > medium > low), then lowest ID.
7. Repeat until N challenges are selected. Skip challenges that would be blocked by other challenges in the candidate list.

Report skipped candidates (both the implicit-blocker reason and priority/wave-already-full reasons) in the final execute summary so the user can see the selection trail.

**If argument is a saga label:**

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json saga show --label=<SAGA_LABEL>
```

Collect all todo challenges in saga order. These will be executed sequentially.

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

### 4a. Setup

Worktrees are mandatory for every challenge — the plugin's `branch-worktree-check.py` hook blocks bare `git checkout -b` / `git switch -c` / `git branch <name>` at tool-use time (by design, to enforce one-worktree-per-branch). `git worktree add -b <name>` is the only supported way to create a challenge branch.

Every worktree is an independent checkout with its own build dir. CMake caches absolute source paths per checkout, so each worktree pays a first-time build (~3–4 min). That cost is inherent to the isolation, not avoidable by branching on main — so the implementer subagent runs `/phoe:build` as its first concrete action (see 4b, step 5 of the subagent prompt).

#### Branch strategy decision (per wave)

Before creating worktrees, decide how challenges in the wave map onto branches. Two patterns:

- **Branch-per-challenge** (default for parallel work) — every challenge gets its own
  `challenge/<label>` branch and worktree. Required when challenges in the wave can run in
  parallel (no dependency edges between them) — they need isolated checkouts to run
  simultaneously without colliding. Each challenge ends up as its own PR, which finalize can
  group or stack as needed.
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

Record the chosen strategy per challenge — it determines what gets written to the finalize
handoff in step 4g. Do not change strategy mid-wave.

For each challenge in the wave:

1. Read the full challenge JSON (run from the main repo root):
   ```bash
   PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
   build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge show --label=<LABEL>
   ```
2. Create the worktree and branch from the main repo root:
   ```bash
   git worktree add .claude/worktrees/challenge-<label> -b challenge/<label>
   ```
3. Move to implementing (run from the main repo root so the crucible binary resolves):
   ```bash
   PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
   build-crucible-${PHOE_ENV}-release/bin/crucible challenge move --label=<LABEL> implementing
   ```

For challenges using the **combined branch** strategy (per the rule above), do NOT create a
new worktree — reuse the existing combined worktree. Skip the `git worktree add` step and
instead `cd` into the existing worktree. Move the challenge to `implementing` as normal.

Each fresh worktree is an independent checkout; `main` is untouched until 4d.

**Parallel-build caching note (bug 8 follow-on).** When a wave has multiple challenges running in parallel, each worktree does a cold build. Configuring ccache project-wide so shared objects are cache hits (~30s vs ~4min rebuild) is a separate optimization tracked outside this command — not part of /phoe:execute's responsibility. See CLAUDE.md "Build Commands" for the worktree build constraint.

### 4b. Implement (parallel within wave)

Dispatch one implementer subagent per challenge. Set the subagent `cwd` to `.claude/worktrees/challenge-<label>`. For multi-challenge waves, also pass `isolation: "worktree"` so each subagent operates in its own worktree checkout.

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

1. **Populate the worktree's build dir.** Your `cwd` is a fresh git worktree with no `build-editor-*/` directory yet. Run `/phoe:build` once as your first action — Forge will configure and build via the active profile. Do this before exploring: you'll want the compilation database present so `grep`/`Read`-based exploration works correctly on modules that use C++23 modules, and so your later `/phoe:verify` run is an incremental build, not a cold one.
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
- Follow the project's coding conventions (CLAUDE.md) — **and before writing any C++, read `references/code-style.md` plus the "Code Guidelines" and "Code Style" sections of the project root `CLAUDE.md`** so the implementation conforms to enforced conventions (namespaces, return-value handling, `auto`, scope spacing, naming, tooling)
- Use plain ASCII only -- no unicode characters
- Use full descriptive variable names -- no abbreviations
- Prefer sized integer types (int32_t, uint64_t) over platform-dependent types
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
| **DONE** | Proceed to 4d (Merge + Verify) |
| **DONE_WITH_CONCERNS** | Read concerns. If about correctness/scope: dispatch a targeted fix subagent. If observational: note and proceed. |
| **BLOCKED** | Retry once: re-read the affected files and any files the subagent mentioned, enrich the prompt with additional context from the codebase, and re-dispatch. On second BLOCKED: mark challenge blocked in Crucible with detailed explanation, write checkpoint to `.claude/handoffs/<LABEL>-checkpoint.md`, **keep the branch and commits intact**. Skip to next challenge. |
| **NEEDS_CONTEXT** | Retry once: read the subagent's questions, answer them by reading the codebase/CLAUDE.md/sibling saga challenges, and re-dispatch with enriched context. On second NEEDS_CONTEXT: mark blocked with unanswered questions as the reason, **keep the branch intact**. Skip. |

When marking a challenge blocked:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible challenge move --label=<LABEL> blocked
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

### 4d. Merge + Verify (sequential, per challenge in ID order)

For each completed challenge:

1. Switch to main and merge:
   ```bash
   git checkout main
   git merge --ff-only challenge/<label>
   ```
   If fast-forward fails (parallel wave): `git merge --no-ff challenge/<label> -m "Merge challenge/<label>"`

2. If merge conflict: `git merge --abort`. Mark the challenge blocked with "Merge conflict with challenge/<other-label> on files: <list>". **Keep the branch intact.** Skip.

3. Run full project verification via `/phoe:verify`. Forge drives the full sequence: configure + build, format check, lint (clang-tidy on changed files), and test.

4. Run challenge-specific verification commands from the challenge JSON.

5. On verify failure: dispatch a fix subagent with the error output. The fix subagent works on main. Re-run `/phoe:verify`. On second failure: mark blocked with the verify error output. **Keep the branch and merged state intact.** Skip.

### 4e. Review (spec + quality in parallel per challenge)

Process challenges in ID order. For each challenge, dispatch both reviewers simultaneously (they are read-only, so parallel dispatch is safe), wait for both to return, then move to the next challenge. Do NOT dispatch reviewers for multiple challenges in parallel — that would let 4f's fix-subagents (which commit to main) race against each other, violating the serialization rule stated in 4f below.

For each verified challenge:

**Spec reviewer** -- launch `invoke-spec-reviewer` agent:

```
Review spec compliance for challenge: <label>

## Acceptance Criteria
<numbered criteria from challenge JSON>

## Strategy
<strategy from challenge JSON, if present>

## Diff
Run: git log --oneline -1 && git diff HEAD~1..HEAD
(or for merge commits: git diff HEAD~1..HEAD)

## Files Changed
<list from git diff --name-only HEAD~1..HEAD>
```

**Quality reviewer** -- launch `invoke-code-reviewer` agent:

```
Review the staged diff (git diff HEAD~1..HEAD) for challenge branch.
Focus on correctness, safety, modern C++23 opportunities, performance,
and project convention compliance. Report findings using
CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
```

### 4f. Handle Review Results

**Serialization rule.** Any subagent in this step commits to `main` (the post-merge state from 4d). If a wave has multiple challenges that need fix or triage subagents, **dispatch them one at a time, not in parallel** — each subagent must finish (commits landed, verify passed) before the next one starts. Parallel dispatch would force each subagent to stash-and-restore its siblings' unstaged edits, a silent data-loss risk if the restore ever fails.

Process challenges in **ID order** within the wave, and for each one:

- **Spec FAIL or quality CRITICAL:** Dispatch a fix subagent with combined feedback from both reviewers. Wait for it to finish. Re-run `/phoe:verify`. Re-dispatch both reviewers. On second failure: mark blocked with reviewer feedback. **Keep all branches and commits intact.** Skip this challenge and move to the next one in the wave.
- **Quality WARNING only:** Proceed. Log warnings in the final report.
- **Quality SUGGESTION:** Dispatch a suggestion-triage subagent with the full suggestion list. For each suggestion the subagent must decide:
  - **Implement it** if it is clearly in-scope, correct, and adds value -- apply the change directly.
  - **Defer it** if it raises a real question, is ambiguous, or is out of scope for this challenge -- emplace a `// TODO: <one-line description of the work that needs doing>` comment at the most relevant code location so it can be evaluated later. Follow the TODO discipline in the plugin's CLAUDE.md: describe the work, not where the note came from; never embed the challenge label, a PR number, a file path, a line number, a branch name, or any other reference that can go stale.

  Suggestions must never be silently dropped. The triage subagent commits any changes (implementations and TODOs) to main. Wait for it to finish. After it returns, re-run `/phoe:verify`. Do NOT re-dispatch the reviewers. Log the triage outcome (implemented / deferred counts) in the final report.
- **Quality NOTE:** Proceed. Log notes in the final report.

### 4g. Finalize

For each successfully reviewed challenge:

1. Move to review: `build-crucible-${PHOE_ENV}-release/bin/crucible challenge move --label=<LABEL> review`
2. **Propagate changes to follow-on saga siblings** -- if the challenge belongs to a saga, reconcile later siblings whose specs may have been invalidated by this implementation (e.g., a rename or API change in this challenge leaves a later sibling's `description`, `strategy`, `affected_files`, or `acceptance_criteria` referring to the old name).
   1. `build-crucible-${PHOE_ENV}-release/bin/crucible --json saga show --label=<SAGA_LABEL>` to list remaining todo + blocked siblings after this challenge's position.
   2. For each later sibling, `build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge show --label=<SIBLING_LABEL>` and scan its text against the committed diff for stale references: renamed types / functions / files, changed signatures, moved modules, replaced concepts.
   3. For each sibling with stale references, `build-crucible-${PHOE_ENV}-release/bin/crucible challenge update --label=<SIBLING_LABEL> [--field=...]` (run `--help` for flags). Keep edits surgical -- update only stale references; do not rewrite scope.
   4. Record sibling updates for the final report (which siblings, which fields). If a later sibling's scope is genuinely broken (not just a rename), do not rewrite it -- flag it as a blocked-follow-on in the report and let the user re-plan.
3. Write the finalize handoff (see 4h below).
4. Clean up the worktree:
   - **branch-per-challenge:** `git worktree remove .claude/worktrees/challenge-<label>` after the last challenge referencing that worktree has been processed.
   - **combined branch:** only remove the shared worktree after the *last* challenge in the combined chain has been processed.
5. **Keep the branch** -- do not delete. The user reviews and decides when to clean up.

**Blocked challenge policy:** Never revert branches or discard commits from blocked challenges. Partial work is valuable context for human resumption via `/phoe:implement <label>`. Always keep branches, commits, and checkpoint files intact.

### 4h. Write finalize handoff

After every challenge that reaches `review` (and once per combined-branch group, after all its
challenges are in `review`), write a handoff file so `/phoe:finalize` knows exactly what landed
and how it should be published.

Path: `.claude/handoffs/finalize/<branch-suffix>.md` — where `<branch-suffix>` is the branch name
with slashes replaced by dashes (`challenge/add-viewport-resize` → `challenge-add-viewport-resize`).
One file per branch. Combined branches hold multiple challenges in a single file.

Create the directory on first write: `mkdir -p .claude/handoffs/finalize`.

```markdown
# Finalize Handoff

## Task type
challenge

## Branch
challenge/<label-or-saga-chain-name>

## Strategy
branch-per-challenge | combined-branch

## Tasks
- <label-1> (status: review)
- <label-2> (status: review)   # only if combined-branch

## Saga
<saga-label>                   # omit if not part of a saga

## Summary
<2–4 bullets: what the branch accomplishes, at a level a reviewer can skim>

## Verification
All challenges passed `/phoe:verify` (build + format + lint + test) before this handoff was
written. Spec and quality review both passed. Any triage outcomes are recorded below.

## Triage outcomes
- <challenge-label>: <implemented count> implemented, <deferred count> deferred as TODOs
   (omit this section if no SUGGESTIONs were triaged)

## Source
/phoe:execute run on <YYYY-MM-DD>
```

Do not include file paths, line numbers, PR numbers, or any detail that will go stale once the
work is merged. The handoff is read once by `/phoe:finalize`, used to pick a publish strategy,
then deleted.

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
```

This feedback file helps the user evolve CLAUDE.md, challenge specs, and the plugin to be more conducive for autonomous operation.

## 6. Report

Print a summary table:

```
/phoe:execute Results
=====================

| Challenge | Wave | Status | Branch | Notes |
|-----------|------|--------|--------|-------|
| add-viewport-resize | 0 | review | challenge/add-viewport-resize | -- |
| forge-compiler | 0 | blocked | challenge/forge-compiler | Build failure: missing include |
| wire-canvas-events | 1 | review | challenge/wire-canvas-events | WARNING: large function |

Saga Progress:
  synthetic-input: 3/6 complete (was 2/6)

Blocked Challenges:
  forge-compiler: Build failure in ForgeCompiler.cpp:42 -- missing include for <filesystem>.
  Checkpoint written to .claude/handoffs/forge-compiler-checkpoint.md
  Resume with: /phoe:implement forge-compiler

Stats: 2 completed, 1 blocked, 0 skipped
Handoffs written to: .claude/handoffs/finalize/ (run /phoe:finalize to publish)
Feedback logged to: .claude/SUBAGENT_FEEDBACK.md
```

Include:
- Saga progress updates for all affected sagas
- Follow-on sibling updates per completed challenge (which siblings, which fields changed), and any flagged-as-broken follow-ons that need user re-planning
- Full explanation for each blocked challenge
- Reference to checkpoint files and how to resume
- Total stats (completed, blocked, skipped)
- The branch strategy chosen per challenge (branch-per-challenge or combined-branch) and the resulting handoff filenames
- Reference to the feedback log
