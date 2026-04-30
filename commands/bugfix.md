---
description: Pick up a Crucible Bug by label (or "next" for highest-severity todo) and fix it end-to-end with verification, stopping at review status.
---

Fix a Crucible Bug end-to-end. Accepts a label or `next` to auto-pick the highest-severity todo bug.

## Arguments

- **`<label>`** — the bug label to fix
- **`next`** — automatically pick the highest-severity `todo` bug

## 1. Bootstrap

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `build-crucible-release/bin/` and match the expected version. A fresh worktree triggers a one-time clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
build-crucible-release/bin/crucible status
```

## 2. Resolve the Bug

**When argument is `next`, first reconcile any bugs currently in `review`.** The user may have merged them since the last session; Crucible does not auto-detect this.

1. List review bugs:

```bash
build-crucible-release/bin/crucible --json bug list --status=review
```

2. For each review bug, probe the local git history for merge evidence (both signals are read-only):

```bash
# Signal A — squash-merge commit on main referencing the label or ID
git log main --oneline -i --grep="<LABEL>"
git log main --oneline --grep="#<ID>"

# Signal B — merge-commit style, where the branch ref is still present locally
git rev-parse --verify bug/<LABEL> 2>/dev/null \
  && git merge-base --is-ancestor bug/<LABEL> main \
  && echo "branch tip is ancestor of main"
```

3. If either signal fires, show the user the matching commit(s) and ask whether to mark the bug done. **Never auto-mark.** On confirmation:

```bash
build-crucible-release/bin/crucible bug move --label=<LABEL> done
```

4. If a review bug shows no merge evidence, leave it in `review`.

Then pick the next todo using severity-aware selection:

1. List all todo bugs:

```bash
build-crucible-release/bin/crucible --json bug list --status=todo
```

2. Pick the best bug using this priority order:
   - **Severity first** — crash > major > moderate > minor
   - **Priority second** — critical > high > medium > low
   - **Lowest ID breaks ties**

3. If no eligible todo bugs exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
build-crucible-release/bin/crucible bug show --label=<LABEL>
```

**Check for existing checkpoint:** Look for `.claude/handoffs/bug-<LABEL>-checkpoint.md`. If found:

1. Read the checkpoint document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the checkpoint summary.
3. Skip Step 6 (Reproduce) and Step 7 (Diagnose) — the checkpoint already contains the diagnosis.
4. Proceed to Step 8 (Fix), using the checkpoint's "remaining work" as the starting point.
5. Delete the checkpoint file once the fix is complete and all verification passes.

## 3. Show Context

Display the bug details: title, description, severity, reproduction steps, acceptance criteria, and verification steps.

## 4. Create a Dedicated Worktree

From the main repo root:

```bash
git worktree add .claude/worktrees/bug-<label> -b bug/<label>
cd .claude/worktrees/bug-<label>
```

Run all subsequent steps from inside the worktree directory.

**Crucible CLI absolute path.** The `build-crucible-release/` directory lives at the *main repo root*, not inside the worktree. Once you `cd` into the worktree, the relative path no longer resolves. Resolve the main-repo-rooted absolute path in every bash block that invokes the CLI:

```bash
CRUCIBLE="$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)/build-crucible-release/bin/crucible"
"$CRUCIBLE" bug show --label=<LABEL>   # or any crucible subcommand
```

All subsequent `build-crucible-release/bin/crucible <args>` snippets in this document assume you've derived `$CRUCIBLE` first — substitute `"$CRUCIBLE" <args>` when running them from inside the worktree.

## 5. Move to In Progress

```bash
build-crucible-release/bin/crucible bug move --label=<LABEL> implementing
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

1. Write `.claude/handoffs/bug-<LABEL>-checkpoint.md`:
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

Implement the fix. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md. **Before writing any C++**, read `references/style-guide.md` and `references/tooling.md` so the fix conforms to the enforced conventions (formatting, naming, comments, namespaces, return-value handling, `auto`, scope spacing, tooling).

When emplacing TODO comments during the fix, follow the discipline in `references/style-guide.md` (TODO Comments section): keep them to one line, describe the work itself, never embed file paths, line numbers, bug labels, PR numbers, branch names, or dates (anything that can go stale), and never leave a TODO that narrates the change you just made.

### Regression Test Evaluation

After implementing the fix, evaluate whether a regression trial is warranted. The goal is to guard against the *class* of flaw recurring — not to mechanically add a test for every bug. Skip when:

- The fix is obviously correct and self-contained (typo, missing null check on a one-off path, wrong literal).
- The bug was in glue or wiring code that will be rewritten rather than maintained.
- The reproduction is inherently unmechanizable (requires specific hardware, manual user interaction, or a platform-only path).

Add a trial when the bug exposes a flaw that could plausibly recur:

- The root cause is a pattern that exists elsewhere in the codebase (e.g., a missed lifetime check, an unhandled enum case, a race on a shared field) — cover the fixed site, and consider whether sibling sites warrant coverage too.
- The fix is subtle enough that a future refactor could silently re-break it.
- The bug stems from a contract or invariant that isn't otherwise enforced by the type system or asserts.
- The repro is mechanizable and cheap to encode as a trial.

When a trial is warranted, launch `invoke-test-engineer` as a subagent to write it. Provide the fix diff, the root cause, and the reproduction steps so the trial exercises the specific flaw — not just the surrounding happy path — and follows Trials conventions.

## 9. Verify

All verification must pass before proceeding:

**a. Reproduction steps no longer trigger the bug** — re-execute the reproduction steps and confirm the bug no longer manifests.

**b. Bug verification steps** — run any commands from the bug's `verification` field.

**c. Full project verification** — run `/phoe:verify` (build + format check + lint + test). All must pass.

**d. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 10. Acceptance Criteria Evaluation

Before committing, systematically evaluate each acceptance criterion from the bug JSON.

1. Retrieve the bug's acceptance criteria: `build-crucible-release/bin/crucible bug show --label=<LABEL>`
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

## 13. Move to Review — Required

Immediately after the commit lands, move the bug to `review`. This is a mandatory, non-skippable final workflow step — the fix is not considered complete until the bug is in `review`:

```bash
build-crucible-release/bin/crucible bug move --label=<LABEL> review
```

If this move fails (server down, label mismatch, Crucible not initialized), **stop and surface the error to the user**. Do not report the bug as fixed, and do not continue to the report step, until the move has succeeded.

## 14. Publish

Push the branch and open a pull request. Confirm with the user before pushing or running
`gh pr create` — these are shared-state actions per CLAUDE.md's Push & Pull Request Workflow.

```bash
git push -u origin bug/<label>
gh pr create \
  --head bug/<label> \
  --base main \
  --title "<bug title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points: the bug, the root cause, the fix>

Crucible: <label>
EOF
)"
```

If the user declines to push, leave the branch local for them to publish later.

If PR review comments come back later, check out the branch, apply fixes, rebuild to confirm
they compile, commit with a brief "Address review: …" message, and push.

## 15. Report

Tell the user:
- What was fixed and the root cause
- Verification results (all passing, reproduction steps no longer trigger)
- Branch name: `bug/<label>`
- Pull request URL (if pushed) or "branch left local; not pushed"
- The bug is now in `review` status — user inspects before marking done

**Do not merge or mark as done.** The user will review and decide.

After the PR lands on remote main, mark the bug done:

```bash
build-crucible-release/bin/crucible bug move --label=<LABEL> done
```

> **Note:** When the user moves a bug to `done`, it is automatically archived in the server's data dir. If work needs to be revisited, use `build-crucible-release/bin/crucible bug unarchive --label=<LABEL>` to restore it to `todo` status.
