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

Follow `references/ensure-binary.md` for the **Crucible** row to guarantee `./crucible` and `./crucible-server` exist and match the expected version. If the procedure stops with a version mismatch, stop here and report it to the user.

Then ensure the Crucible server is running (the CLI is a client; commands fail if the server is down):

```bash
./crucible-server --headless &
```

Confirm Crucible is initialized for this project:

```bash
./crucible status
```

Verify workspace is clean:

```bash
git status --porcelain
```

If there are uncommitted changes, stop and tell the user to commit or stash first.

Fetch remote main and fast-forward if needed:

```bash
git fetch origin main
git log main..origin/main --oneline
```

If there are new commits, fast-forward: `git checkout main && git pull --ff-only origin main`.

## 2. Resolve Challenges

**If argument is a number N or "next":**

Use saga-aware priority logic to select N eligible challenges:

1. List all sagas: `./crucible --json saga list`
2. List all todo challenges: `./crucible --json challenge list --status=todo`
3. Auto-unblock any blocked challenges whose blockers are now merged:
   ```bash
   ./crucible --json challenge list --status=blocked
   ```
   For each, check if the `blocked_by` challenge is now merged. If so: `./crucible challenge unblock <ID> todo`
4. For each candidate, check saga ordering -- only pick challenges whose saga predecessors are all `merged` or `canceled`.
5. Among eligible candidates, pick by: priority (critical > high > medium > low), then lowest ID.
6. Repeat until N challenges are selected. Skip challenges that would be blocked by other challenges in the candidate list.

**If argument is a saga label:**

```bash
./crucible --json saga show --label=<SAGA_LABEL>
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

For each challenge in the wave:

1. Read the full challenge JSON: `./crucible --json challenge show --label=<LABEL>`
2. Create worktree and branch from the main repo root: `git worktree add .claude/worktrees/challenge-<label> -b challenge/<label>`
3. Move to implementing: `./crucible challenge move --label=<LABEL> implementing`

Each worktree is an independent checkout; `main` is untouched.

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

1. Read the affected files and explore related code to understand the context
2. Follow the strategy steps (if provided) or plan your own approach
3. Implement the changes
4. Write tests if your implementation introduces new public interfaces or non-trivial logic
   - Tests are NOT needed for: build system changes, config changes, pure wiring/delegation
5. Run the build: cmake --build build/ -j24
   - Fix any compilation errors before proceeding
6. Run tests: ctest --test-dir build/ --output-on-failure
   - Fix any test failures
7. Self-review against each acceptance criterion
8. Commit your changes with a descriptive message referencing the challenge label
9. Report back

## Constraints
- Do NOT enter plan mode
- Do NOT ask the user questions -- if you need information, read the codebase
- Do NOT modify files outside the challenge's scope unless absolutely necessary
- Follow the project's coding conventions (CLAUDE.md)
- Use plain ASCII only -- no unicode characters
- Use full descriptive variable names -- no abbreviations
- Prefer sized integer types (int32_t, uint64_t) over platform-dependent types

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
./crucible challenge move --label=<LABEL> blocked
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

3. Run full project verification via `/phoe:verify`:
   - Build (cmake)
   - Format (clang-format)
   - Lint (clang-tidy on changed files)
   - Test (ctest)

4. Run challenge-specific verification commands from the challenge JSON.

5. On verify failure: dispatch a fix subagent with the error output. The fix subagent works on main. Re-run `/phoe:verify`. On second failure: mark blocked with the verify error output. **Keep the branch and merged state intact.** Skip.

### 4e. Review (spec + quality in parallel)

For each verified challenge, dispatch BOTH reviewers simultaneously:

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

- **Spec FAIL or quality CRITICAL:** Dispatch a fix subagent with combined feedback from both reviewers. Re-run `/phoe:verify`. Re-dispatch both reviewers. On second failure: mark blocked with reviewer feedback. **Keep all branches and commits intact.** Skip.
- **Quality WARNING only:** Proceed. Log warnings in the final report.
- **Quality SUGGESTION/NOTE:** Proceed. Ignore.

### 4g. Finalize

For each successfully reviewed challenge:

1. Move to review: `./crucible challenge move --label=<LABEL> review`
2. Clean up worktree: `git worktree remove .claude/worktrees/challenge-<label>`
3. **Keep the branch** -- do not delete. The user reviews and decides when to clean up.

**Blocked challenge policy:** Never revert branches or discard commits from blocked challenges. Partial work is valuable context for human resumption via `/phoe:implement <label>`. Always keep branches, commits, and checkpoint files intact.

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
Feedback logged to: .claude/SUBAGENT_FEEDBACK.md
```

Include:
- Saga progress updates for all affected sagas
- Full explanation for each blocked challenge
- Reference to checkpoint files and how to resume
- Total stats (completed, blocked, skipped)
- Reference to the feedback log
