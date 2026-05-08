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

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `build-crucible-release/bin/` and match the expected version. A fresh worktree triggers a one-time clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
build-crucible-release/bin/crucible status
```

## 2. Resolve the Challenge

**When argument is `next`, first reconcile any challenges currently in `review`.** The user may have merged them since the last session; Crucible does not auto-detect this.

1. List review challenges:

```bash
build-crucible-release/bin/crucible --json challenge list --status=review
```

2. For each review challenge, probe the local git history for merge evidence (both signals are read-only):

```bash
# Signal A — squash-merge commit on main referencing the label or ID
git log main --oneline -i --grep="<LABEL>"
git log main --oneline --grep="#<ID>"

# Signal B — merge-commit style, where the branch ref is still present locally
git rev-parse --verify challenge/<LABEL> 2>/dev/null \
  && git merge-base --is-ancestor challenge/<LABEL> main \
  && echo "branch tip is ancestor of main"
```

3. If either signal fires, show the user the matching commit(s) and ask whether to mark the challenge merged. **Never auto-mark.** On confirmation:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> merged
```

4. If a review challenge shows no merge evidence, leave it in `review` — it is still under human review.

Then pick the next todo using saga-aware selection:

1. List all sagas and their progress:

```bash
build-crucible-release/bin/crucible --json saga list
```

2. List all todo challenges:

```bash
build-crucible-release/bin/crucible --json challenge list --status=todo
```

3. Pick the best challenge using this priority order:
   - **Saga ordering first** — if a challenge belongs to a saga, only pick it if all earlier challenges in that saga are `merged` or `canceled`. Never skip ahead in a saga's ordering.
   - **Blocked check** — if a saga predecessor is in `review` or `implementing` (not yet merged), the next challenge cannot proceed. Move it to `blocked` and stop:
     ```bash
     build-crucible-release/bin/crucible challenge block <NEXT_ID> --blocked_by=<PREDECESSOR_ID> --reason="Awaiting merge of #<PREDECESSOR_ID> on branch challenge/<predecessor-label>"
     ```
     Tell the user which challenge is blocked and why, then try the next eligible challenge. If no unblocked challenges remain, stop.
   - **Priority second** — among eligible challenges, pick the highest priority (critical > high > medium > low).
   - **Lowest ID breaks ties** — if still tied, pick the lowest ID.

4. Also check `blocked` challenges: for each, verify if the blocker is now `merged`. If so, auto-unblock:
   ```bash
   build-crucible-release/bin/crucible challenge unblock <ID> todo
   ```
   Then include the unblocked challenge in the candidate pool.

5. If no eligible todo challenges exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
build-crucible-release/bin/crucible challenge show --label=<LABEL>
```

**Check for existing checkpoint:** Look for `.claude/handoffs/<LABEL>-checkpoint.md`. If found:

1. Read the checkpoint document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the checkpoint summary.
3. Skip Step 7 (Explore and Understand) — the checkpoint already contains the exploration results.
4. Proceed to Step 8 (Plan and Implement), using the checkpoint's "remaining work" as the starting point.
5. Delete the checkpoint file once implementation is complete and all verification passes.

## 3. Show Context

Display the challenge details: title, description, acceptance criteria, and verification steps.

**Check for saga membership** — search the saga list for the resolved challenge ID. If it belongs to a saga:

```bash
build-crucible-release/bin/crucible saga show --label=<SAGA_LABEL>
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

## 5. Create a Dedicated Worktree

From the main repo root:

```bash
git worktree add .claude/worktrees/challenge-<label> -b challenge/<label>
cd .claude/worktrees/challenge-<label>
```

Run all subsequent steps from inside the worktree directory.

**Crucible CLI absolute path.** The `build-crucible-release/` directory lives at the *main repo root*, not inside the worktree. Once you `cd` into the worktree, the relative path no longer resolves. Resolve the main-repo-rooted absolute path in every bash block that invokes the CLI:

```bash
CRUCIBLE="$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)/build-crucible-release/bin/crucible"
"$CRUCIBLE" challenge show --label=<LABEL>   # or any crucible subcommand
```

All subsequent `build-crucible-release/bin/crucible <args>` snippets in this document assume you've derived `$CRUCIBLE` first — substitute `"$CRUCIBLE" <args>` when running them from inside the worktree.

## 6. Move to Implementing

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> implementing
```

## 7. Explore and Understand

Read the challenge's affected files, references, and tags. Explore the codebase to understand what needs to change. If the challenge belongs to a saga, review completed sibling challenges for patterns and context.

### Context Checkpoint

If this challenge is complex (multiple modules, many affected files, or extensive exploration required), consider writing a checkpoint after exploration and before implementation:

1. Write `.claude/handoffs/<LABEL>-checkpoint.md`:
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
2. Tell the user: "This challenge is consuming significant context. I've written a checkpoint to `.claude/handoffs/<LABEL>-checkpoint.md`. Start a new session and run `/phoe:implement <LABEL>` to continue with fresh context."
3. Stop. Do not continue implementation in the current session.

**When to checkpoint:** Use judgment. Natural breakpoints include: after exploration but before implementation, or after implementing half the changes when the remaining work is still substantial. The goal is to avoid coherence loss on large tasks.

## 8. Plan and Implement

Enter plan mode, create an implementation plan, then execute it. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md. **Before writing any C++**, read `references/style-guide.md` and `references/tooling.md` so the implementation conforms to the enforced conventions (formatting, naming, comments, namespaces, return-value handling, `auto`, scope spacing, tooling). If the challenge has a `strategy` field, use it as a starting point for the implementation plan.

Comments: default to none. Prefer one line; two or three for the genuinely complex. *Why*, not *what*. Paragraphs belong in the commit message. Full rules in `references/style-guide.md` §Comments.

When emplacing TODO comments during implementation, follow the discipline in `references/style-guide.md` (TODO Comments section): keep them to one line, describe the work itself, never embed file paths, line numbers, challenge labels, PR numbers, branch names, or dates (anything that can go stale), and never leave a TODO that narrates the refactor or rename you just performed.

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

1. Retrieve the challenge's acceptance criteria: `build-crucible-release/bin/crucible challenge show --label=<LABEL>`
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

## 13. Move to Review — Required

Immediately after the commit lands, move the challenge to `review`. This is a mandatory, non-skippable final workflow step — implementation is not considered complete until the challenge is in `review`:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> review
```

If this move fails (server down, label mismatch, Crucible not initialized), **stop and surface the error to the user**. Do not report the challenge as done, and do not continue to the report step, until the move has succeeded.

## 14. Propagate Changes to Follow-on Challenges

If this challenge belongs to a saga, reconcile its siblings — the implementation may have invalidated assumptions baked into later challenge specs (e.g., this challenge renamed a core type that a later challenge references by its old name, or changed a file path, function signature, or module boundary that a later challenge's `description`, `strategy`, `acceptance_criteria`, or `affected_files` mentions explicitly).

1. List remaining siblings (todo + blocked) in the saga, after this challenge's position:
   ```bash
   build-crucible-release/bin/crucible --json saga show --label=<SAGA_LABEL>
   ```
2. For each later sibling, fetch its full spec:
   ```bash
   build-crucible-release/bin/crucible --json challenge show --label=<SIBLING_LABEL>
   ```
3. Scan each sibling's text for stale references against the diff this challenge produced. Things to look for:
   - Type / class / function / method names that were renamed
   - File paths that moved or were split
   - API signatures or parameter names that changed
   - Module or layer boundaries that shifted
   - Concepts the sibling depends on that no longer exist or have been replaced
4. For each sibling with stale references, update the affected fields:
   ```bash
   build-crucible-release/bin/crucible challenge update --label=<SIBLING_LABEL> [--description=... --strategy=... --affected_files=...]
   ```
   Run `build-crucible-release/bin/crucible challenge update --help` for the exact flags. Keep edits surgical — update only the references that are actually stale; do not rewrite specs or scope.
5. If a sibling has no stale references, leave it alone.
6. Record which siblings were updated (and what fields changed) for the report.

Do not edit the implementation itself from this step — this is metadata reconciliation only. If the implementation surfaced a real scope problem in a later challenge (not a rename), note it in the report and let the user decide whether to re-plan.

## 15. Publish

Push the branch and open a pull request. Confirm with the user before pushing or running
`gh pr create` — these are shared-state actions per CLAUDE.md's Push & Pull Request Workflow.

```bash
git push -u origin challenge/<label>
gh pr create \
  --head challenge/<label> \
  --base main \
  --title "<challenge title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points describing what the branch accomplishes>

Crucible: #<id> <label>
Saga: #<saga-id> <saga-label>
EOF
)"
```

`Crucible:` and `Saga:` trailers are mandatory; pull IDs from the JSON already fetched in Step 2/3. Drop the `Saga:` line for orphans.

Compose the summary from the challenge title and the key changes — keep it concise; the
challenge spec in Crucible is the detailed record. If the user declines to push, leave the
branch local for them to publish later.

If PR review comments come back later, check out the branch, apply fixes, rebuild to confirm
they compile (full `/phoe:verify` only when changes are significant — new logic, API changes,
new files), commit with a brief "Address review: …" message, and push.

## 15.5. Watch CI

If a PR was pushed, run the watch loop in `references/ci-watch.md` against it.

## 16. Report

If the challenge belongs to a saga, show updated saga progress:

```bash
build-crucible-release/bin/crucible saga show --label=<SAGA_LABEL>
```

Tell the user:
- What was implemented
- Tests added (list test names) or why tests were not applicable
- Verification results (all passing)
- Branch name: `challenge/<label>`
- Saga progress (if applicable)
- Follow-on sibling updates, if any (which siblings were updated and what fields changed)
- Pull request URL (if pushed) or "branch left local; not pushed"
- The challenge is now in `review` status — user inspects before marking merged

**Do not merge or mark as merged.** The user will review and decide whether to merge, request changes, or mark merged.

After the PR lands on remote main, mark the challenge merged:

```bash
build-crucible-release/bin/crucible challenge move --label=<LABEL> merged
```

Use `/phoe:plan` to create new challenges or extend an existing saga.

> **Note:** When the user moves a challenge to `merged`, it is automatically archived in the server's data dir. If work needs to be revisited, use `build-crucible-release/bin/crucible challenge unarchive --label=<LABEL>` to restore it to `todo` status.
