---
description: Pick up a Crucible Challenge by label (or "next" for highest-priority saga-aware todo) and implement it end-to-end with verification, stopping at review status.
---

Implement a Crucible Challenge end-to-end with human supervision. Accepts a label or `next` to auto-pick the highest-priority todo respecting saga ordering.

> **This is the human-supervised workflow.** For fully autonomous execution of multiple challenges, use `/phoe:execute`.

## Arguments

- **`<label>`** — the challenge label to implement
- **`next`** — automatically pick the highest-priority `todo` challenge, respecting saga ordering
- *(no argument)* — if no todo challenges exist, prompt the user to run `/phoe:plan` first

## 1. Bootstrap

Verify the Crucible binary exists:

```bash
./crucible status
```

If `./crucible` is missing, build with `/phoe:build` (using `-DAPPLICATION=Crucible`), then copy the binary from `build/bin/crucible` to the project root.

## 2. Resolve the Challenge

**If argument is `next`**, use saga-aware selection:

1. List all sagas and their progress:

```bash
./crucible --json saga list
```

2. List all todo challenges:

```bash
./crucible --json challenge list --status=todo
```

3. Pick the best challenge using this priority order:
   - **Saga ordering first** — if a challenge belongs to a saga, only pick it if all earlier challenges in that saga are `merged` or `canceled`. Never skip ahead in a saga's ordering.
   - **Blocked check** — if a saga predecessor is in `review` or `implementing` (not yet merged), the next challenge cannot proceed. Move it to `blocked` and stop:
     ```bash
     ./crucible challenge block <NEXT_ID> --blocked_by=<PREDECESSOR_ID> --reason="Awaiting merge of #<PREDECESSOR_ID> on branch challenge/<predecessor-label>"
     ```
     Tell the user which challenge is blocked and why, then try the next eligible challenge. If no unblocked challenges remain, stop.
   - **Priority second** — among eligible challenges, pick the highest priority (critical > high > medium > low).
   - **Lowest ID breaks ties** — if still tied, pick the lowest ID.

4. Also check `blocked` challenges: for each, verify if the blocker is now `merged`. If so, auto-unblock:
   ```bash
   ./crucible challenge unblock <ID> todo
   ```
   Then include the unblocked challenge in the candidate pool.

5. If no eligible todo challenges exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
./crucible challenge show --label=<LABEL>
```

**Check for existing handoff:** Look for `.crucible/handoffs/<LABEL>-checkpoint.md`. If found:

1. Read the handoff document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the handoff summary.
3. Skip Step 7 (Explore and Understand) — the handoff already contains the exploration results.
4. Proceed to Step 8 (Plan and Implement), using the handoff's "remaining work" as the starting point.
5. Delete the handoff file once implementation is complete and all verification passes.

## 3. Show Context

Display the challenge details: title, description, acceptance criteria, and verification steps.

**Check for saga membership** — search the saga list for the resolved challenge ID. If it belongs to a saga:

```bash
./crucible saga show --label=<SAGA_LABEL>
```

Show the saga name, where this challenge sits in the ordering, and overall saga progress. This gives full feature context for the implementation.

## 4. Conditional Remote Sync

Fetch remote main to check for recent changes:

```bash
git fetch origin main
git log main..origin/main --oneline
```

If there are new commits on remote main, review the changed files and commit messages. Evaluate whether the changes overlap with the current challenge's affected files, tags, or description.

- **If relevant** — fast-forward main before branching:

```bash
git checkout main
git pull --ff-only origin main
```

- **If unrelated** — skip the pull and branch from current local main. No sync needed.

## 5. Create a Dedicated Branch

```bash
git checkout -b challenge/<label>
```

## 6. Move to Implementing

```bash
./crucible challenge move --label=<LABEL> implementing
```

## 7. Explore and Understand

Read the challenge's affected files, references, and tags. Explore the codebase to understand what needs to change. If the challenge belongs to a saga, review completed sibling challenges for patterns and context.

### Context Checkpoint

If this challenge is complex (multiple modules, many affected files, or extensive exploration required), consider writing a checkpoint after exploration and before implementation:

1. Write `.crucible/handoffs/<LABEL>-checkpoint.md`:
   ```markdown
   # Checkpoint: <LABEL>
   ## Challenge
   <title and one-line description>
   ## Understanding
   <key findings from exploration — what code does what, dependencies, patterns found>
   ## Decisions
   <design choices made and why>
   ## Implemented So Far
   <files changed, what was done — empty if checkpointing before implementation>
   ## Remaining Work
   <concrete steps still needed>
   ## Open Questions
   <anything needing user input>
   ```
2. Tell the user: "This challenge is consuming significant context. I've written a checkpoint to `.crucible/handoffs/<LABEL>-checkpoint.md`. Start a new session and run `/phoe:implement <LABEL>` to continue with fresh context."
3. Stop. Do not continue implementation in the current session.

**When to checkpoint:** Use judgment. Natural breakpoints include: after exploration but before implementation, or after implementing half the changes when the remaining work is still substantial. The goal is to avoid coherence loss on large tasks.

## 8. Plan and Implement

Enter plan mode, create an implementation plan, then execute it. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md. If the challenge has a `strategy` field, use it as a starting point for the implementation plan.

### Unit Test Coverage

After implementing the feature code, evaluate whether unit tests are needed. Tests are required when the implementation introduces:

- New public interfaces (classes, functions, or API surface that other code will call)
- Non-trivial logic (algorithms, state machines, parsing, validation, calculations)
- Behavior changes to existing logic that alter observable outcomes

Tests are NOT required for:

- Build system or CMake-only changes
- Configuration file changes (JSON, cfg)
- Pure wiring or delegation (forwarding calls to already-tested functions)
- Platform-specific code that can only be tested on the target platform's CI

When tests are applicable, launch `invoke-test-engineer` as a subagent to write them. Provide it with the implementation diff and the module context so it can place tests correctly and follow Trials conventions.

## 9. Verification Gate

All verification must pass before proceeding:

**a. Challenge verification steps** — run any commands from the challenge's `verification` field (shown in the challenge JSON).

**b. Full project verification** — run `/phoe:verify` (build + format check + lint + test). All must pass.

**c. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 10. Acceptance Criteria Evaluation

Before committing, systematically evaluate each acceptance criterion from the challenge JSON. The model that wrote the code must not self-approve without structured evaluation.

1. Retrieve the challenge's acceptance criteria: `./crucible challenge show --label=<LABEL>`
2. For **each** criterion, answer explicitly:
   - **Met?** Yes / No / Partially
   - **Evidence:** What in the diff proves this? (file:line, test name, or command output)
   - **Unverifiable?** If the criterion cannot be verified mechanically (e.g., "feels responsive"), flag it for human review.
3. If any criterion is clearly **unmet**, fix the implementation and re-run `/phoe:verify` before continuing.
4. List any criteria flagged as **unverifiable** — these will be included in the report for the user.

5. **Test coverage check** — if the implementation introduced testable logic (per the criteria in Step 8), verify that corresponding tests exist and pass. If tests were expected but missing, go back and add them before continuing.

Do not proceed to code review until all mechanically-verifiable criteria are met.

## 11. Automated Code Review

Invoke the code reviewer as a **separate agent** to evaluate the implementation diff. The agent that wrote the code must not be the only judge.

1. Stage all changes: `git add -A`
2. Launch `invoke-code-reviewer` as a subagent with the prompt:
   > Review the staged diff (`git diff --cached`) for this challenge branch. Focus on correctness, safety, modern C++23 opportunities, performance, and project convention compliance. Report findings using CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
3. **Gate on zero CRITICAL findings.** If any CRITICAL issues are found:
   - Fix each CRITICAL issue
   - Re-run `/phoe:verify`
   - Re-run acceptance criteria evaluation (Step 10)
   - Re-invoke the code reviewer (repeat this step)
4. **WARNING findings** are included in the final report for user review but do not block the commit.
5. **SUGGESTION and NOTE findings** are omitted from the report unless particularly insightful.

## 12. Commit Changes

Commit all changes on the challenge branch with a descriptive message referencing the challenge label.

## 13. Report

Move the challenge to review status:

```bash
./crucible challenge move --label=<LABEL> review
```

If the challenge belongs to a saga, show updated saga progress:

```bash
./crucible saga show --label=<SAGA_LABEL>
```

Tell the user:
- What was implemented
- Tests added (list test names) or why tests were not applicable
- Verification results (all passing)
- Branch name: `challenge/<label>`
- Saga progress (if applicable)
- The challenge is now in `review` status — user inspects before marking merged

**Do not merge or mark as merged.** The user will review and decide whether to merge, request changes, or mark merged.

Use `/phoe:plan` to create new challenges or extend an existing saga.

> **Note:** When the user moves a challenge to `merged`, it is automatically archived to `.crucible/archive/`. If work needs to be revisited, use `./crucible challenge unarchive --label=<LABEL>` to restore it to `todo` status.
