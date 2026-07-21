---
description: Pick up a Crucible Bug by label (or "next" for highest-severity todo) and fix it end-to-end with verification, stopping at review status.
---

Fix a Crucible Bug end-to-end. Accepts a label or `next` to auto-pick the highest-severity todo bug.

## Arguments

- **`<label>`** — the bug label to fix
- **`next`** — automatically pick the highest-severity `todo` bug

## 1. Bootstrap

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/` and match the expected version. The first build is a clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible status
```

## 2. Resolve the Bug

**When argument is `next`, first reconcile any bugs currently in `review`.** The user may have merged them since the last session; Crucible does not auto-detect this.

1. List review bugs:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible --json bug list --status=review
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

3. If either signal fires, show the user the matching commit(s) and ask whether to mark the bug merged. **Never auto-mark.** On confirmation:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug move --label=<LABEL> merged
```

4. If a review bug shows no merge evidence, leave it in `review`.

Then pick the next todo using severity-aware selection:

1. List all todo bugs:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible --json bug list --status=todo
```

2. Pick the best bug using this priority order:
   - **Severity first** — crash > major > moderate > minor
   - **Priority second** — critical > high > medium > low
   - **Lowest ID breaks ties**

3. If no eligible todo bugs exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug show --label=<LABEL>
```

**Check for existing checkpoint:** Look for `.claude/handoffs/bug-<LABEL>-checkpoint.md`. If found:

1. Read the checkpoint document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the checkpoint summary.
3. Skip Step 6 (Reproduce) and Step 7 (Diagnose) — the checkpoint already contains the diagnosis.
4. Proceed to Step 8 (Fix), using the checkpoint's "remaining work" as the starting point.
5. Delete the checkpoint file once the fix is complete and all verification passes.

### Claim the bug immediately

The moment you've resolved *which* bug to work — before showing context or branching — **move it to
`active`** so a parallel session cannot pick up the same work:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug move --label=<LABEL> active
```

This is a claim, not a commitment: if reproduction fails (Step 6) or you decide not to proceed, move
it back with `... bug move --label=<LABEL> todo`.

## 3. Show Context

Display the bug details: title, description, severity, reproduction steps, acceptance criteria, and verification steps.

## 4. Create a Dedicated Worktree

From the main repo root, create the worktree and branch (this exact `git worktree add` form is what
the plugin's `branch-worktree-check.py` hook blesses):

```bash
git worktree add .claude/worktrees/bug-<label> -b bug/<label>
```

Then **enter it with the `EnterWorktree` tool** — `EnterWorktree(path=".claude/worktrees/bug-<label>")`.
In a background session, Claude Code's isolation guard refuses native `Write`/`Edit` in any worktree
the session has not entered through the harness, forcing slow Bash/heredoc edits; `EnterWorktree(path=...)`
registers the worktree with the guard so native file tools keep working. It enters *by path* without
taking removal ownership, so a later `git worktree remove .claude/worktrees/bug-<label>` (after the
PR merges) still works normally; if this session entered via `EnterWorktree`, `ExitWorktree(keep)`
first. (Do not create the worktree with `EnterWorktree(name=...)` — that mints its own branch/path
naming and breaks the `bug/<label>` convention.)

**Bootstrap Forge in the worktree** so the first `/phoe:verify` is incremental, not a cold failure —
a fresh worktree can lack its own `Applications/Forge/.bootstrap-out/forge`:

```bash
python3 Applications/Forge/Scripts/bootstrap.py
```

Run all subsequent steps from inside the worktree directory.

**Crucible CLI absolute path.** The Crucible CLI is built into the main repo's Forge output tree (`Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/`), not the worktree's. Once you `cd` into the worktree, the relative path resolves against the worktree's own (empty) output tree. Resolve the main-repo-rooted absolute path in every bash block that invokes the CLI:

```bash
CRUCIBLE="$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)/Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible"
"$CRUCIBLE" bug show --label=<LABEL>   # or any crucible subcommand
```

All subsequent `Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible <args>` snippets in this document assume you've derived `$CRUCIBLE` first — substitute `"$CRUCIBLE" <args>` when running them from inside the worktree.

## 5. Confirm Active

The bug was claimed as `active` back in Step 2 (before branching), so there is nothing to move here.
If reproduction (Step 6) fails or you abandon the bug, revert the claim:

```bash
# only if abandoning — otherwise the bug is already active
"$CRUCIBLE" bug move --label=<LABEL> todo
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

Implement the fix. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md. **Before writing any C++**, read `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` and `${CLAUDE_PLUGIN_ROOT}/references/tooling.md` so the fix conforms to the enforced conventions (formatting, naming, comments, namespaces, return-value handling, `auto`, scope spacing, tooling).

Comments: default to none. Prefer one line; two or three for the genuinely complex. *Why*, not *what*. Paragraphs belong in the commit message. Full rules in `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` §Comments.

When emplacing TODO comments during the fix, follow the discipline in `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` (TODO Comments section): keep them to one line, describe the work itself, never embed file paths, line numbers, bug labels, PR numbers, branch names, or dates (anything that can go stale), and never leave a TODO that narrates the change you just made.

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

1. Retrieve the bug's acceptance criteria: `Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug show --label=<LABEL>`
2. For **each** criterion, answer explicitly:
   - **Met?** Yes / No / Partially
   - **Evidence:** What in the diff proves this? (file:line, test name, or command output)
   - **Unverifiable?** If the criterion cannot be verified mechanically, flag it for human review.
3. If any criterion is clearly **unmet**, fix and re-verify.

## 11. Automated Code Review

Invoke the code reviewer as a **separate agent** to evaluate the implementation diff.

1. **Freeze the diff — commit first, then review a SHA.** Never hand a reviewer "the staged diff":
   the index mutates as you keep working, so a finding filed against `--cached` can land on code a
   later edit already superseded. Commit the fix on the bug branch now, then capture the frozen SHA
   and the review base:
   ```bash
   git fetch origin main                          # so the merge-base below is current
   git add -A
   git commit -m "<descriptive message referencing the bug label>"
   REVIEW_SHA=$(git rev-parse HEAD)
   REVIEW_BASE=$(git merge-base origin/main HEAD)  # the branch's actual fork point — NOT hardcoded main
   ```
   Because the commit already lands here, Step 12 is a no-op unless the fix loop below adds commits.
2. Capture the bug contract verbatim — the reviewer cannot reach Crucible from the worktree, and this gate blocks on CRITICAL/WARNING, so a reviewer without the criteria invents the contract and then blocks on it:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug show --label=<LABEL>
```

   Interpolate that whole output — title, description, reproduction steps, acceptance criteria, verification — into the prompt under a `## Bug Contract (verbatim from Crucible)` heading. Do not summarize. Resolve any `Docs/*.md §x` reference the bug cites: confirm it exists in this worktree, and say so explicitly in the prompt if it does not.

3. Launch `invoke-code-reviewer` as a subagent with the prompt:
   > Review the change on this bug fix branch. Focus on correctness, safety, modern C++23 opportunities, performance, and project convention compliance. Verify the fix addresses the root cause and doesn't introduce regressions. Report findings using CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
   >
   > [Include the **Bug Contract** captured above here, verbatim.]
   >
   > Lint already ran in Step 9's `/phoe:verify` (`forge lint`, clang-tidy over the changed surface, module-import graph included) and passed — do not re-adjudicate include/import hygiene or punt to `invoke-lint-agent` unless you see a concrete contradiction.
   >
   > **Reading the change.** You are reviewing a **frozen commit range** — the orchestrator has filled `<SHA>` with the committed tip (`REVIEW_SHA`) and `<BASE>` with `git merge-base origin/main HEAD` (`REVIEW_BASE`, the branch's actual fork point, never a hardcoded `main`). Do not pipe a whole diff. `git diff <BASE>..<SHA> --stat` gives you the map; read each changed file **in place**, and use `git diff <BASE>..<SHA> -- <path>` per file for the delta. A whole-diff dump on a 30 KB+ change overflows the Bash output cap, spills to a temp file, then overflows the Read cap. The range is immutable for the life of your review.
   >
   > **Where to search.** This repository holds many sibling worktrees under `.claude/worktrees/` and build trees under `.forge*/` and `.bootstrap-out/`, all carrying near-identical copies of the same sources. Scope every search to the worktree root you were given. Prefer `git grep`, which searches only tracked files in the current tree. If you use `grep -r`/`find`, exclude `.forge*/`, `.bootstrap-out/`, and `.claude/worktrees/`.
   >
   > **How to search.** Bash runs under **zsh**: an unquoted `--include=*.h` that matches nothing aborts the whole command with "no matches found". Quote every glob-bearing flag or use `git grep -n <pattern> -- '<pathspec>'`. **Empty output may mean the command never ran** — confirm it executed before concluding a symbol is absent.
   >
   > **Paths.** Use full repo-relative paths. A git pathspec that matches nothing **exits 0 with empty output**, which is indistinguishable from "no changes here". Before reporting anything as missing or unreferenced, re-run the check with the scoping above and state which tree you searched.
4. **Gate on zero CRITICAL and zero WARNING findings.** If any CRITICAL or WARNING issues are found:
   - Fix each CRITICAL and WARNING issue
   - Commit the fix on the branch and **re-freeze**: `REVIEW_SHA=$(git rev-parse HEAD)` (refresh `REVIEW_BASE` too if `origin/main` moved)
   - Re-run `/phoe:verify`
   - Re-run acceptance criteria evaluation (Step 10)
   - Re-invoke the code reviewer against the new SHA
5. **WARNING is a blocking tier alongside CRITICAL** — fix each one as in step 4, or surface it to the user for an explicit waive if you judge it a false positive or out of scope. Never ship a WARNING unaddressed; record any waived WARNING in the final report.

## 12. Finalize the Commit

The fix was already committed in Step 11 (the freeze), and every review-fix pass added its own
commit. So there is normally nothing to commit here — the branch already carries the work with a
message referencing the bug label. Optionally squash review fixups into one for a tidy history; do
**not** leave any change uncommitted going into Step 13.

## 13. Move to Review — Required

Immediately after the commit lands, move the bug to `review`. This is a mandatory, non-skippable final workflow step — the fix is not considered complete until the bug is in `review`:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug move --label=<LABEL> review
```

If this move fails (server down, label mismatch, Crucible not initialized), **stop and surface the error to the user**. Do not report the bug as fixed, and do not continue to the report step, until the move has succeeded.

## 14. Publish

Push the branch and open a pull request. Confirm with the user before pushing or running
`gh pr create` — these are shared-state actions per CLAUDE.md's Push & Pull Request Workflow.

```bash
git push -u origin bug/<label>
PR_URL=$(gh pr create \
  --head bug/<label> \
  --base main \
  --title "<bug title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points: the bug, the root cause, the fix>

Crucible: <label>
EOF
)")
```

After a successful `gh pr create`, record the review link on the bug so future sessions
and `crucible bug show` surface the PR URL without grepping comments. The flag name is
intentionally source-neutral — `--replace-review-link` accepts any URL string, so a
non-GitHub review system fits without rewording this step:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug update --label=<LABEL> --replace-review-link="${PR_URL}"
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
- The bug is now in `review` status — user inspects before it lands

**Do not merge the PR yourself, and do not mark the bug `merged` before the merge has landed.** The user decides whether to merge, request changes, or close. The `review` → `merged` transition tracks reality; it must not run ahead of it.

But once the PR is confirmed merged into remote `main`, reconciling the tracking status *is* expected — a merged PR left in `review` is stale bookkeeping. Verify the landing first (PR `state` is `MERGED` **and** its merge commit is reachable from `origin/main`), then move it without waiting to be asked again:

```bash
Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug move --label=<LABEL> merged
```

> **Note:** When the user moves a bug to `merged`, it is automatically archived in the server's data dir. If work needs to be revisited, use `Applications/Forge/.forge-out/shared-engine-ci-linux-Headless/bin/crucible bug unarchive --label=<LABEL>` to restore it to `todo` status.
