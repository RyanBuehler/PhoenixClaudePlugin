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

Run `/phoe:build crucible` so both `crucible` and `crucible-server` exist and match the expected version. The first build is a clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

**Locate the Crucible CLI — discover it, don't hardcode a path.** Forge places the binary in a per-profile subtree whose name varies with host and build config, under both the configured build tree (`Applications/Forge/.forge/`) and the bootstrap output (`Applications/Forge/.forge-out/`) — take the **newest**, since a stale `.forge-out/` copy still reports a plausible version, so resolve it into `$CRUCIBLE` and use `"$CRUCIBLE"` in every crucible call below. Each Bash block is a fresh shell, so the variable will not carry across the separate blocks — re-run this `find` (or substitute the path it resolved) in each block that calls the CLI:

```bash
CRUCIBLE=$(find Applications/Forge/.forge Applications/Forge/.forge-out -type f \
    -path '*/bin/crucible' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
[ -x "$CRUCIBLE" ] || { echo "crucible not found — run /phoe:build crucible first"; exit 1; }
```

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `"$CRUCIBLE"` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
"$CRUCIBLE" status
```

## 2. Resolve the Challenge

**When argument is `next`, first reconcile any challenges currently in `review`.** The user may have merged them since the last session; Crucible does not auto-detect this.

1. List review challenges:

```bash
"$CRUCIBLE" --json challenge list --status=review
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
"$CRUCIBLE" challenge move --label=<LABEL> merged
```

   Then clean up the stale worktree and branch per Step 17's "On merge" note; the
   saga-aware selection below surfaces the next ready challenge.

4. If a review challenge shows no merge evidence, leave it in `review` — it is still under human review.

Then pick the next todo using saga-aware selection:

1. List all sagas and their progress:

```bash
"$CRUCIBLE" --json saga list
```

2. List all todo challenges:

```bash
"$CRUCIBLE" --json challenge list --status=todo
```

3. Pick the best challenge using this priority order:
   - **Saga ordering first** — if a challenge belongs to a saga, only pick it if all earlier challenges in that saga are `merged` or `canceled`. Never skip ahead in a saga's ordering.
   - **Blocked check** — if a saga predecessor is in `review` or `active` (not yet merged), the next challenge cannot proceed. Move it to `blocked` and stop:
     ```bash
     "$CRUCIBLE" challenge block <NEXT_ID> --blocked_by=<PREDECESSOR_ID> --reason="Awaiting merge of #<PREDECESSOR_ID> on branch challenge/<predecessor-label>"
     ```
     Tell the user which challenge is blocked and why, then try the next eligible challenge. If no unblocked challenges remain, stop.
   - **Priority second** — among eligible challenges, pick the highest priority (critical > high > medium > low).
   - **Lowest ID breaks ties** — if still tied, pick the lowest ID.

4. Also check `blocked` challenges: for each, verify if the blocker is now `merged`. If so, auto-unblock:
   ```bash
   "$CRUCIBLE" challenge unblock <ID> todo
   ```
   Then include the unblocked challenge in the candidate pool.

5. If no eligible todo challenges exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
"$CRUCIBLE" challenge show --label=<LABEL>
```

**Check for existing checkpoint:** Look for `.claude/handoffs/<LABEL>-checkpoint.md`. If found:

1. Read the checkpoint document.
2. Display: "Resuming from checkpoint — here's where we left off:" followed by the checkpoint summary.
3. Skip Step 7 (Explore and Understand) — the checkpoint already contains the exploration results.
4. Proceed to Step 8 (Plan and Implement), using the checkpoint's "remaining work" as the starting point.
5. Delete the checkpoint file once implementation is complete and all verification passes.

### Claim the challenge immediately

The moment you've resolved *which* challenge to work — before showing context, syncing, or
branching — **move it to `active`** so a parallel session cannot pick up the same work:

```bash
"$CRUCIBLE" challenge move --label=<LABEL> active
```

This is a claim, not a commitment: if you decide during exploration (Steps 3–5) not to proceed, move
it back with `... challenge move --label=<LABEL> todo`. Everything below runs against the now-active
challenge.

## 3. Show Context

Display the challenge details: title, description, acceptance criteria, and verification steps.

**Read the challenge's comments — they outrank the description:**

```bash
"$CRUCIBLE" challenge comments --label=<LABEL>
```

A challenge sits in the backlog while the tree moves under it, so a comment recording an intervening
rename or a behavior that landed since is newer than the description and wins wherever the two
disagree. Where they do, say so — name the stale description text and what you followed instead —
rather than reconciling it silently.

**Check for saga membership** — search the saga list for the resolved challenge ID. If it belongs to a saga:

```bash
"$CRUCIBLE" saga show --label=<SAGA_LABEL>
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

From the main repo root, create the worktree and branch (this exact `git worktree add` form is what
the plugin's `branch-worktree-check.py` hook blesses — it enforces `<type>/<label>` naming at
`.claude/worktrees/<type>-<label>`):

```bash
git worktree add .claude/worktrees/challenge-<label> -b challenge/<label>
```

Then **enter it with the `EnterWorktree` tool** — `EnterWorktree(path=".claude/worktrees/challenge-<label>")`.
This is not cosmetic. In a background session, Claude Code's isolation guard refuses native
`Write`/`Edit` in any worktree the session has not entered through the harness ("parent bg session
hasn't isolated yet"), which forces slow, error-prone Bash/heredoc edits on you and every subagent
you dispatch. `EnterWorktree(path=...)` registers the worktree with the guard so native file tools
keep working. It enters *by path* without taking removal ownership, so Step 17's `git worktree
remove` cleanup still applies unchanged. (Do not create the worktree with `EnterWorktree(name=...)`
instead — that mints its own branch/path naming and cannot base on a specific ref, breaking the
`challenge/<label>` convention the rest of this workflow relies on.)

**Bootstrap Forge in the worktree.** A fresh worktree — even one branched from a warm checkout — can
lack its own `Applications/Forge/.bootstrap-out/forge`. Bootstrap it now so the first `/phoe:verify`
is an incremental build, not a cold failure:

```bash
python3 Applications/Forge/Scripts/bootstrap.py
```

Run all subsequent steps from inside the worktree directory.

**Crucible CLI in the worktree.** The Crucible CLI was built into the *main* repo's Forge output, not the worktree's — a worktree's own `.forge-out/` is empty until it builds. So re-resolve `$CRUCIBLE` against the main repo root (discovered via the git common dir, never hardcoded):

```bash
MAIN_ROOT=$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)
CRUCIBLE=$(find "$MAIN_ROOT/Applications/Forge/.forge" "$MAIN_ROOT/Applications/Forge/.forge-out" \
    -type f -path '*/bin/crucible' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
"$CRUCIBLE" challenge show --label=<LABEL>   # or any crucible subcommand
```

Every `"$CRUCIBLE" <args>` snippet below assumes you've derived `$CRUCIBLE` this way first.

## 6. Confirm Active

The challenge was claimed as `active` back in Step 2 (before branching), so there is nothing to move
here — this is just the checkpoint where, if exploration or the worktree setup made you abandon the
challenge, you revert the claim:

```bash
# only if abandoning — otherwise the challenge is already active
"$CRUCIBLE" challenge move --label=<LABEL> todo
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

Enter plan mode, create an implementation plan, then execute it. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md. **Before writing any C++**, read `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` and `${CLAUDE_PLUGIN_ROOT}/references/tooling.md` so the implementation conforms to the enforced conventions (formatting, naming, comments, namespaces, return-value handling, `auto`, scope spacing, tooling). `${CLAUDE_PLUGIN_ROOT}` is the plugin install path (fall back to `~/phoenixclaudeplugin/references/` if it is unset). If the challenge has a `strategy` field, use it as a starting point for the implementation plan.

Comments: default to none. Prefer one line; two or three for the genuinely complex. *Why*, not *what*. Paragraphs belong in the commit message. Full rules in `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` §Comments.

When emplacing TODO comments during implementation, follow the discipline in `${CLAUDE_PLUGIN_ROOT}/references/style-guide.md` (TODO Comments section): keep them to one line, describe the work itself, never embed file paths, line numbers, challenge labels, PR numbers, branch names, or dates (anything that can go stale), and never leave a TODO that narrates the refactor or rename you just performed.

### Unit Test Coverage

After implementing the feature code, evaluate whether unit tests are needed. Tests are required when the implementation introduces:

- New public interfaces (classes, functions, or API surface that other code will call)
- Non-trivial logic (algorithms, state machines, parsing, validation, calculations)
- Behavior changes to existing logic that alter observable outcomes

Tests are NOT required for:

- Build-system or profile/config-only changes
- Configuration file changes (JSON, cfg)
- Pure wiring or delegation (forwarding calls to already-tested functions)
- Platform-specific code that can only be tested on the target platform's CI

> **Subagent worktree isolation.** `invoke-test-engineer` carries `isolation: worktree`, so the
> harness drops it in a *fresh* worktree branched from `main` — without this challenge's
> still-uncommitted changes, so it cannot read the code under test and resorts to copying files in.
> Every dispatch below therefore passes the absolute path of this challenge worktree
> (`.claude/worktrees/challenge-<label>`). **The dispatch vehicle differs by job:** the test-writing
> dispatch here needs to write, so it goes as a **general-purpose** subagent; the review dispatches
> in Steps 11 and 12 are **read-only** and go as `Explore`. Do not merge the two — and note that
> `invoke-code-reviewer` is not a read-only vehicle despite the name: it carries `Bash`. See
> `${CLAUDE_PLUGIN_ROOT}/references/dispatch-briefs.md` §1. Keep the specialist prompts below
> verbatim; only the vehicle changes.

When tests are applicable, launch `invoke-test-engineer` as a subagent to write them. Provide it with the implementation diff and the module context so it can place tests correctly and follow Trials conventions. **Ask it to end its report with a `## Workflow Friction` section** listing anything that made the task harder than it should have been — missing context, ambiguous spec, undocumented convention, tooling gaps — or the single word `none` if nothing applied. These notes are aggregated in Step 14.5.

## 9. Verification Gate

All verification must pass before proceeding:

**a. Challenge verification steps** — run any commands from the challenge's `verification` field (shown in the challenge JSON).

**b. Full project verification** — run `/phoe:verify` (configure → build → format-check → lint →
policy audits → test). All must pass. `/phoe:verify` covers **one profile**: if this challenge touched
anything under `Applications/Forge/`, or edited a build profile, verify that profile explicitly too —
a green editor verify does not run Forge's own trials and has twice hidden a broken one.

**c. A cold build outlives the command timeout** and gets backgrounded by the harness. Wait on it
properly — capture the PID or the log, scoped to this worktree — per
`${CLAUDE_PLUGIN_ROOT}/references/dispatch-briefs.md` §4. A process-name match is either unscoped
(never finishes) or silently matches nothing (returns instantly, looking like a completed build).

**d. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 10. Acceptance Criteria Evaluation

Before committing, systematically evaluate each acceptance criterion from the challenge JSON. The model that wrote the code must not self-approve without structured evaluation.

1. Retrieve the challenge's acceptance criteria: `"$CRUCIBLE" challenge show --label=<LABEL>`
2. For **each** criterion, answer explicitly:
   - **Met?** Yes / No / Partially
   - **Evidence:** What in the diff proves this? (file:line, test name, or command output)
   - **Unverifiable?** If the criterion cannot be verified mechanically (e.g., "feels responsive"), flag it for human review.
3. If any criterion is clearly **unmet**, fix the implementation and re-run `/phoe:verify` before continuing.
4. List any criteria flagged as **unverifiable** — these will be included in the report for the user.

5. **Test coverage check** — if the implementation introduced testable logic (per the criteria in Step 8), verify that corresponding tests exist and pass. If tests were expected but missing, go back and add them before continuing.

Do not proceed to code review until all mechanically-verifiable criteria are met.

## 10.5. Review Dispatch Preamble — include in every reviewer prompt

Steps 11 and 12 both dispatch reviewer subagents, and both gate on zero CRITICAL and zero WARNING
findings. The brief they receive is assembled per
`${CLAUDE_PLUGIN_ROOT}/references/dispatch-briefs.md`, which is the single source for these blocks —
read it before dispatching. Every failure mode it prevents **fails in the direction of a false
clean**: a reviewer that cannot find something reports it as absent, and that conclusion reaches the
PR body.

### 10.5a. Ship the contract — never a paraphrase

The challenge body lives server-side in Crucible and is not reachable from the worktree, so a
reviewer that cannot read the acceptance criteria **invents the contract from the code and fixtures,
then blocks on it**. Capture the challenge verbatim before dispatching:

```bash
"$CRUCIBLE" challenge show <ID>
```

Interpolate that **whole output** into the reviewer prompt under a
`## Challenge Contract (verbatim from Crucible)` heading — do not summarize, and do not re-word the
acceptance criteria. Then resolve the design-doc references and assemble the build-state block per
`dispatch-briefs.md` §2, which also covers the two brief-assembly rules this workflow must follow:
**resolve `REVIEW_BASE`/`REVIEW_SHA` with `git rev-parse` / `git merge-base` at dispatch time**
(never transcribe or hand-extend a hash), and **generate the reviewer's file list from the range**
with `git diff --name-only`, never from the challenge's `Files` field.

### 10.5b. The preamble itself

Paste `dispatch-briefs.md` §3 — **Review dispatch preamble** — verbatim into each reviewer prompt,
substituting the resolved `REVIEW_BASE`/`REVIEW_SHA` for its `<BASE>`/`<SHA>` placeholders. It
covers reading the frozen commit rather than the working tree, the path and pathspec hazards, the
command guard, the zsh traps, and the requirement that every cited path and symbol be resolved
before it is reported.

### 10.5c. Dispatch read-only

Both review dispatches go as `Explore` with the absolute path of this challenge worktree — never as
a write-capable agent. `dispatch-briefs.md` §1 has the rationale and the read-only clause to include
in the prompt.

## 11. Automated Code Review

Invoke the code reviewer as a **separate agent** to evaluate the implementation diff. The agent that wrote the code must not be the only judge.

1. **Freeze the diff — commit first, then review a SHA.** Never hand a reviewer "the staged diff":
   the index mutates as you keep working, so a finding filed against `--cached` can land on code a
   later edit already superseded (one saga had 3 of 6 review passes report on stale code this way).
   Commit the work on the challenge branch now, then capture the frozen SHA and the review base:
   ```bash
   git fetch origin main                          # so the merge-base below is current
   git add -A
   git commit -m "<descriptive message referencing the challenge label>"
   REVIEW_SHA=$(git rev-parse HEAD)
   REVIEW_BASE=$(git merge-base origin/main HEAD)  # the branch's actual fork point — NOT hardcoded
                                                   # main; a stacked/diverged branch reviewed against
                                                   # main shows a predecessor's merged work as noise
   ```
   Because the commit already lands here, Step 13 is a no-op unless the fix loop below adds commits.
2. Dispatch the reviewer **read-only** (`Explore`, Step 10.5c) with the absolute path of this
   challenge worktree, using the prompt:
   > Review the change on this challenge branch. Focus on correctness, safety, modern C++23 opportunities, performance, and project convention compliance. Report findings using CRITICAL/WARNING/SUGGESTION/NOTE severity levels.
   >
   > [Include the **Challenge Contract** (Step 10.5a), the **review dispatch preamble** (Step 10.5b) and the **read-only clause** (Step 10.5c) here, verbatim — substituting the resolved `REVIEW_BASE` and `REVIEW_SHA` values for the `<BASE>..<SHA>` placeholders so the reviewer diffs the frozen range.]
   >
   > End your report with a `## Workflow Friction` section listing anything that made this review harder than it should have been — missing context, ambiguous spec, undocumented convention, tooling gaps — or the single word `none` if nothing applied.
3. **Gate on zero CRITICAL and zero WARNING findings.** If any CRITICAL or WARNING issues are found:
   - Resolve every path and symbol each finding cites before acting on it
     (`${CLAUDE_PLUGIN_ROOT}/references/dispatch-briefs.md` §5) — findings routinely name paths that
     do not exist while being otherwise correct. Say so when a citation does not resolve, and
     re-locate the real target rather than fixing the nearest plausible thing.
   - Fix each CRITICAL and WARNING issue
   - Commit the fix on the branch and **re-freeze**: `REVIEW_SHA=$(git rev-parse HEAD)` (refresh `REVIEW_BASE` too if `origin/main` moved)
   - Re-run `/phoe:verify`
   - Re-run acceptance criteria evaluation (Step 10)
   - Re-invoke the code reviewer against the new SHA (repeat this step)
4. **WARNING is a blocking tier alongside CRITICAL.** If you judge a WARNING to be a false positive or genuinely out of scope, do not silently proceed — surface it to the user with your reasoning and let them waive it. Record any waived WARNING in the final report; never ship one unaddressed.
5. **SUGGESTION and NOTE findings** are omitted from the report unless particularly insightful.

## 12. Adversarial Review — Required Before PR

After the standard review passes, dispatch an **adversarial** reviewer subagent. The standard review asks "is this code well-formed?"; the adversarial review asks "how does this break?". A PR cannot be opened until this gate has run and any CRITICAL findings are resolved.

Dispatch a fresh **read-only** subagent (`Explore`, Step 10.5c) with the absolute path of this
challenge worktree and the prompt:

> Adversarially review the change on challenge `<LABEL>`. Your job is to attack this implementation, not validate it. Assume the standard review already passed — do not duplicate it.
>
> [Include the **Challenge Contract** (Step 10.5a), the **review dispatch preamble** (Step 10.5b) and the **read-only clause** (Step 10.5c) here, verbatim — substituting the resolved `REVIEW_BASE` and `REVIEW_SHA` values for the `<BASE>..<SHA>` placeholders. Use the same frozen SHA the standard review ran against.]
>
> Hunt for:
>
> - **Edge cases the implementation does not handle** — empty input, max-size input, unicode, negative values, NaN, integer overflow, signed/unsigned mismatches, off-by-one at boundaries.
> - **Concurrency hazards** — races, reentrancy, ordering assumptions across threads or subsystems, lifetime invariants not enforced by the type system.
> - **Silent failure modes** — code paths that swallow errors, no-op on the unexpected branch, or fail to log via Scribe (violates the no-silent-failures rule).
> - **Hidden coupling** — state shared across modules, ownership confusion, assumptions about call order or initialization sequence.
> - **Performance pathologies under realistic load** — allocation in hot paths, O(n²) under expected n, lock contention, cache-hostile access patterns.
> - **Spec gaps** — acceptance criteria that pass for the easy case but fail in plausible variations the spec did not enumerate. If the spec itself is the weak link, say so.
>
> Report only findings that represent real failure modes, not stylistic concerns. Use CRITICAL/WARNING/SUGGESTION/NOTE severity. If you find nothing actionable, say so explicitly — a clean adversarial pass is a valid result.
>
> End your report with a `## Workflow Friction` section listing anything that made this review harder than it should have been — missing context, ambiguous spec, undocumented convention, tooling gaps — or the single word `none` if nothing applied.

**Gate on zero CRITICAL and zero WARNING adversarial findings.** Treat them the same as Step 11: fix every CRITICAL and WARNING, commit the fix and re-freeze (`REVIEW_SHA=$(git rev-parse HEAD)`), re-run `/phoe:verify`, re-run acceptance criteria evaluation, then re-run **both** the standard and adversarial reviews against the new SHA until both pass. As in Step 11, a WARNING you judge a false positive or out of scope must be surfaced to the user for an explicit waive — never silently dropped — and any waived WARNING recorded in the final report.

## 13. Finalize the Commit

The implementation was already committed in Step 11 (the freeze), and every review-fix pass added
its own commit. So there is normally nothing to commit here — the branch already carries the work
with a message referencing the challenge label. If review produced a string of small fixup commits
and you want a tidy history, optionally squash them into one before moving on; do **not** leave any
change uncommitted going into Step 14.

## 14. Move to Review — Required

Immediately after the commit lands, move the challenge to `review`. This is a mandatory, non-skippable final workflow step — implementation is not considered complete until the challenge is in `review`:

```bash
"$CRUCIBLE" challenge move --label=<LABEL> review
```

If this move fails (server down, label mismatch, Crucible not initialized), **stop and surface the error to the user**. Do not report the challenge as done, and do not continue to the report step, until the move has succeeded.

## 14.5. Subagent Feedback Log

Collect the `## Workflow Friction` sections from each subagent report dispatched during this run (test engineer from Step 8, standard reviewer from Step 11, adversarial reviewer from Step 12). If every section is `none` or empty, skip this step entirely — write nothing.

Otherwise, append to `.claude/SUBAGENT_FEEDBACK.md` at the main repo root (same file
`/phoe:execute` writes to).

**Append with Bash, never `Write`/`Edit`.** In a background session the isolation guard refuses the
native file tools for repo paths the parent has not entered, and gitignored `.claude/` is covered.
That guard is **tool-scoped, not path-scoped**: Bash redirection is not intercepted, so the append
succeeds with no permission prompt and this step needs no user approval. A refused `Write` means
reach for Bash; it never means the step is impossible.

```bash
cat >> .claude/SUBAGENT_FEEDBACK.md <<'ENTRY'

## <YYYY-MM-DD> - /phoe:implement <label>
<the collected sections, in the format below>
ENTRY
```

The same `>>` creates the file when it does not exist. Do not `Write` it: the log reaches hundreds
of KB and a whole-file write discards every prior entry.

Use this format, omitting subagents whose section was `none`:

```markdown
## <YYYY-MM-DD> - /phoe:implement <label>

### Challenge: <label> (test-engineer)
- <friction item 1>
- <friction item 2>

### Challenge: <label> (code-reviewer)
- <friction item>

### Challenge: <label> (adversarial-reviewer)
- <friction item>
```

Do not summarize, paraphrase, or filter the friction items — copy them verbatim. The user reviews this log on their own schedule to evolve CLAUDE.md, challenge specs, and the plugin.

Do not mention this log in the Step 17 report.

## 15. Propagate Changes to Follow-on Challenges and Docs

Reconcile anything this implementation may have invalidated — later saga-sibling specs (if this challenge is in a saga) **and** `docs/` design/spec files (always, even for orphans): a renamed type, moved file, changed signature, or replaced concept that a later sibling's `description` / `strategy` / `acceptance_criteria` / `affected_files`, or a doc, still references by its old name.

1. If in a saga, list remaining siblings (todo + blocked) after this challenge's position:
   ```bash
   "$CRUCIBLE" --json saga show --label=<SAGA_LABEL>
   ```
2. For each later sibling, fetch its full spec:
   ```bash
   "$CRUCIBLE" --json challenge show --label=<SIBLING_LABEL>
   ```
3. Scan each sibling's text — and grep `docs/` design/spec files — for stale references against the diff this challenge produced. Things to look for:
   - Type / class / function / method names that were renamed
   - File paths that moved or were split
   - API signatures or parameter names that changed
   - Module or layer boundaries that shifted
   - Concepts the sibling depends on that no longer exist or have been replaced
4. Fix each surgically — `"$CRUCIBLE" challenge update --label=<SIBLING_LABEL> [--description=... --strategy=... --affected_files=...]` (run `--help` for flags) for challenge text; an in-place edit on this challenge's branch (rides the same PR) for docs. Update only the references that are actually stale; do not rewrite specs or scope.
5. **Comment on every open challenge whose ground this work moved** — sibling or orphan, and in
   addition to any `challenge update`. The trigger is landing work that renames, moves, or supersedes
   something the challenge points at. Record what moved to what name, and which behaviors introduced
   since must not be dropped by the eventual rewrite. Editing the words fixes the text; the comment is
   what tells the implementer the ground moved at all, and what a rewrite would otherwise silently
   drop.
   ```bash
   "$CRUCIBLE" challenge comment --label=<OTHER_LABEL> --body="<what moved; what must not be dropped>"
   ```
6. If a sibling or doc has no stale references, leave it alone.
7. Record which siblings + docs were updated (and what fields/files changed) for the report.

This is the pre-merge pass; the authoritative pass re-runs post-merge in Step 17. Do not edit the implementation itself from this step — metadata + docs reconciliation only. If the implementation surfaced a real scope problem in a later challenge (not a rename), note it in the report and let the user decide whether to re-plan.

## 16. Publish

Push the branch and open a pull request. Confirm with the user before pushing or running
`gh pr create` — these are shared-state actions per CLAUDE.md's Push & Pull Request Workflow.

```bash
git push -u origin challenge/<label>
PR_URL=$(gh pr create \
  --head challenge/<label> \
  --base main \
  --title "<challenge title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points describing what the branch accomplishes>

Crucible: #<id> <label>
Saga: #<saga-id> <saga-label>
EOF
)")
PR_NUM="${PR_URL##*/}"
echo "Opened PR #${PR_NUM}: ${PR_URL}"
```

After a successful `gh pr create`, record the review link on the challenge so future
sessions and `crucible challenge show` surface the PR URL without grepping comments.
The flag name is intentionally source-neutral — `--replace-review-link` accepts any
URL string, so a non-GitHub review system (Gitea, Phabricator, internal mirror) fits
without rewording this step:

```bash
"$CRUCIBLE" challenge update --label=<LABEL> --replace-review-link="${PR_URL}"
```

`Crucible:` and `Saga:` trailers are mandatory; pull IDs from the JSON already fetched in Step 2/3. Drop the `Saga:` line for orphans.

Refer to the PR as **PR #<N>** (the trailing `/pull/<N>` segment) in all subsequent narration and the report — never URL alone.

Compose the summary from the challenge title and the key changes — keep it concise; the
challenge spec in Crucible is the detailed record. If the user declines to push, leave the
branch local for them to publish later.

If PR review comments come back later, check out the branch, apply fixes, rebuild to confirm
they compile (full `/phoe:verify` only when changes are significant — new logic, API changes,
new files), commit with a brief "Address review: …" message, and push.

## 17. Report

If the challenge belongs to a saga, show updated saga progress:

```bash
"$CRUCIBLE" saga show --label=<SAGA_LABEL>
```

Tell the user:
- What was implemented
- Tests added (list test names) or why tests were not applicable
- Verification results (all passing)
- Branch name: `challenge/<label>`
- Saga progress (if applicable)
- Follow-on sibling updates, if any (which siblings were updated and what fields changed)
- Reconciliation outcome (pre-merge pass, Step 15): siblings + `docs/` scanned against the committed diff — which were updated, or "none stale" (required — a present line makes a skipped reconciliation visible). The authoritative post-merge pass runs later when the PR lands and reports its own outcome then.
- Pull request: **PR #<N>** + URL (or "branch left local; not pushed"). Always lead with `PR #<N>`.
- The challenge is now in `review` status — user inspects before it lands

**Do not merge the PR yourself, and do not mark the challenge `merged` before the merge has landed.** The user decides whether to merge, request changes, or close. The `review` → `merged` transition tracks reality; it must not run ahead of it.

But once the PR is confirmed merged into remote `main` — typically observed on a later `/phoe:implement next` (Step 2) — reconciling the tracking status *is* expected; a merged PR left in `review` is stale bookkeeping (and saga progress only counts `merged`). Verify the landing first (PR `state` is `MERGED` **and** its merge commit is reachable from `origin/main` — a retarget-miss can show `MERGED` without reaching main), then move it to `merged` and run the **end-of-cycle reconciliation** (the authoritative pass) against the merged diff:

```bash
"$CRUCIBLE" challenge move --label=<LABEL> merged
```

Re-scan the merged diff against remaining todo/blocked siblings **and** `docs/` design/spec files for stale references the Step 15 pass missed. Fix challenge text in place with `crucible challenge update`, and comment (Step 15, item 5) on any challenge whose ground the merged diff moved. For stale docs, file a tracked docs-reconcile challenge (`/phoe:plan`) so the edit flows through the normal implement path rather than an untracked side PR — this challenge's branch is gone post-merge. Flag genuinely scope-broken siblings as blocked rather than rewriting them. Report this pass's outcome when it runs.

### On merge — clean up and surface the next challenge

Whenever this challenge's PR is confirmed merged (here or in Step 2's
reconciliation), after the reconciliation pass above, clean up and report — then
**stop**; do not begin the next challenge:

1. **Clean up the worktree and branch** from the main repo root (skip either if
   already gone):
   ```bash
   git worktree remove .claude/worktrees/challenge-<label>
   git branch -D challenge/<label>
   ```
   If this session entered the worktree via `EnterWorktree(path=...)` in Step 5, first
   `ExitWorktree(keep)` to return to the main checkout — then the `git worktree
   remove` above is safe. (Entering by path takes no removal ownership, so
   `ExitWorktree` will not remove it for you.)

2. **Report the next ready challenge — do not implement it.** If the merged
   challenge was in a saga, use Step 2's saga-aware selection (ordering satisfied,
   no unmerged predecessor, auto-unblock whatever the merge unblocked) to find the
   next pickup, and report its label, title, priority, and `/phoe:implement
   <label>`. Present it for the user to pick up; do not start it. If the saga is
   done or nothing is unblocked, say so.

Use `/phoe:plan` to create new challenges or extend an existing saga.

> **Note:** When the user moves a challenge to `merged`, it is automatically archived in the server's data dir. If work needs to be revisited, use `"$CRUCIBLE" challenge unarchive --label=<LABEL>` to restore it to `todo` status.
