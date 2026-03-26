---
description: Pick up a Crucible Bug by label (or "next" for highest-severity todo) and fix it end-to-end with verification, stopping at review status.
---

Fix a Crucible Bug end-to-end. Accepts a label or `next` to auto-pick the highest-severity todo bug.

## Arguments

- **`<label>`** — the bug label to fix
- **`next`** — automatically pick the highest-severity `todo` bug

## 1. Bootstrap

Verify the Crucible binary exists:

```bash
./Crucible status
```

If this fails, build it from source with `/phoe:build` and copy the binary to the project root.

## 2. Resolve the Bug

**If argument is `next`**, use severity-aware selection:

1. List all todo bugs:

```bash
./Crucible --json bug list --status=todo
```

2. Pick the best bug using this priority order:
   - **Severity first** — crash > major > moderate > minor
   - **Priority second** — critical > high > medium > low
   - **Lowest ID breaks ties**

3. If no eligible todo bugs exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
./Crucible bug show --label=<LABEL>
```

**Check for existing handoff:** Look for `.crucible/handoffs/bug-<LABEL>-checkpoint.md`. If found:

1. Read the handoff document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the handoff summary.
3. Skip Step 6 (Reproduce) and Step 7 (Diagnose) — the handoff already contains the diagnosis.
4. Proceed to Step 8 (Fix), using the handoff's "remaining work" as the starting point.
5. Delete the handoff file once the fix is complete and all verification passes.

## 3. Show Context

Display the bug details: title, description, severity, reproduction steps, acceptance criteria, and verification steps.

## 4. Create a Dedicated Branch

```bash
git checkout -b bug/<label>
```

## 5. Move to In Progress

```bash
./Crucible bug move --label=<LABEL> in_progress
```

## 6. Reproduce

Follow the bug's reproduction steps exactly:

1. Execute each reproduction step as described.
2. Confirm the bug manifests as described.
3. Document the exact observed behavior — what happens, any error messages, stack traces, or log output.

If the bug **cannot be reproduced**, tell the user and stop. Do not proceed with a speculative fix.

## 7. Diagnose

Invoke the `superpowers:systematic-debugging` skill to trace the root cause:

1. Start from the reproduction evidence (crash location, error message, observed behavior).
2. Trace through the code to identify the root cause.
3. Document the root cause clearly — what code is wrong and why it produces the observed behavior.

### Context Checkpoint

If diagnosis is consuming significant context, write a checkpoint before implementing the fix:

1. Write `.crucible/handoffs/bug-<LABEL>-checkpoint.md`:
   ```markdown
   # Checkpoint: bug-<LABEL>
   ## Bug
   <title and one-line description>
   ## Reproduction
   <what was observed when reproducing>
   ## Root Cause
   <identified root cause with file:line references>
   ## Proposed Fix
   <approach to fix the bug>
   ## Remaining Work
   <concrete steps to implement the fix>
   ```
2. Tell the user: "This bug diagnosis is consuming significant context. I've written a checkpoint. Start a new session and run `/phoe:bugfix <LABEL>` to continue."
3. Stop.

## 8. Fix

Implement the fix. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md.

## 9. Verify

All verification must pass before proceeding:

**a. Reproduction steps no longer trigger the bug** — re-execute the reproduction steps and confirm the bug no longer manifests.

**b. Bug verification steps** — run any commands from the bug's `verification` field.

**c. Full project verification** — run `/phoe:verify` (build + format check + lint + test). All must pass.

**d. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 10. Acceptance Criteria Evaluation

Before committing, systematically evaluate each acceptance criterion from the bug JSON.

1. Retrieve the bug's acceptance criteria: `./Crucible bug show --label=<LABEL>`
2. For **each** criterion, answer explicitly:
   - **Met?** Yes / No / Partially
   - **Evidence:** What in the diff proves this? (file:line, test name, or command output)
   - **Unverifiable?** If the criterion cannot be verified mechanically, flag it for human review.
3. If any criterion is clearly **unmet**, fix and re-verify.

## 11. Automated Code Review

Invoke the code reviewer as a **separate agent** to evaluate the implementation diff.

1. Stage all changes: `git add -A`
2. Launch `invoke-code-reviewer` as a subagent with the prompt:
   > Review the staged diff (`git diff --cached`) for this bug fix branch. Focus on correctness, safety, modern C++23 opportunities, performance, and project convention compliance. Verify the fix addresses the root cause and doesn't introduce regressions. Report findings using CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
3. **Gate on zero CRITICAL findings.** If any CRITICAL issues are found:
   - Fix each CRITICAL issue
   - Re-run `/phoe:verify`
   - Re-run acceptance criteria evaluation (Step 10)
   - Re-invoke the code reviewer
4. **WARNING findings** are included in the final report.

## 12. Commit Changes

Commit all changes on the bug branch with a descriptive message referencing the bug label.

## 13. Report

Move the bug to review status:

```bash
./Crucible bug move --label=<LABEL> review
```

Tell the user:
- What was fixed and the root cause
- Verification results (all passing, reproduction steps no longer trigger)
- Branch name: `bug/<label>`
- The bug is now in `review` status — user inspects before marking done

**Do not merge or mark as done.** The user will review and decide.

> **Note:** When the user moves a bug to `done`, it is automatically archived to `.crucible/bug-archive/`. If work needs to be revisited, use `./Crucible bug unarchive --label=<LABEL>` to restore it to `todo` status.
