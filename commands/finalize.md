---
description: Finalize completed challenges and bugs into remote main via PR — reads handoffs, analyzes branch topology, recommends PR strategy, pushes, creates PRs, addresses review feedback, and tracks post-merge Crucible status.
---

Finalize completed Crucible challenges and bugs into remote main. Reads handoffs left by
`/phoe:execute`, `/phoe:implement`, and `/phoe:bugfix`, analyzes branch topology, recommends a
PR strategy, creates PRs after user approval, addresses PR review comments, and tracks
post-merge status updates.

> **Verification is the implementing agent's responsibility.** Tasks arriving in `review` status have already passed `/phoe:verify` (build + format + lint + test). This command does not re-run the full verification suite. When addressing PR review comments, rebuild to confirm the fix compiles. Only re-run `/phoe:verify` if the changes are significant enough to warrant it (e.g., logic changes, new files, API modifications).

> **Lifecycle terms.** Challenges terminate at `merged`. Bugs terminate at `done`. The CLI has
> separate `challenge` and `bug` subcommands; their status verbs do not interchange. See the
> "Crucible Lifecycle Reference" section in the plugin's CLAUDE.md.

## Arguments

- *(no argument)* — assess all `review`-status challenges and bugs and recommend a finalization strategy
- **`<label>`** — finalize a specific challenge or bug (type is inferred from the branch prefix and handoff)
- **`landed <label> [<label2> ...]`** — mark one or more tasks as terminal after their PR lands on remote main (translates to `merged` for challenges, `done` for bugs)
- **`merged <label> [<label2> ...]`** — alias for `landed`, kept for backwards compatibility

Determine which mode by checking if the first word is `landed` or `merged` (post-merge tracking), otherwise treat as assessment/finalization mode.

## 1. Bootstrap

Run `/phoe:build crucible` to ensure `crucible` and `crucible-server` exist under `build-crucible-${PHOE_ENV}-release/bin/` and match the expected version.

Resolve the environment suffix (include at the top of every bash block that touches a binary):

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
```

Confirm Crucible is reachable:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible status
```

## 2. Assess State

### 2a. Read finalize handoffs

The implementing commands (`/phoe:execute`, `/phoe:implement`, `/phoe:bugfix`) drop a handoff
file per branch into `.claude/handoffs/finalize/` describing what landed and how it should be
published.

```bash
ls .claude/handoffs/finalize/ 2>/dev/null
```

Read every handoff file. Each one tells you: the task type (`challenge` or `bug`), the branch
name, the strategy hint (`branch-per-challenge`, `branch-per-bug`, or `combined-branch`), the
tasks the branch carries, the saga (if any), and a short summary.

If the handoff directory is empty or missing, fall back to listing `review`-status tasks
directly (step 2b). Handoffs are an optimization, not a requirement — older work may not have
them.

### 2b. Gather review tasks (challenges and bugs)

Always list both, even when handoffs are present, to catch anything the user moved to `review`
manually since the last implementing run:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge list --status=review
build-crucible-${PHOE_ENV}-release/bin/crucible --json bug list --status=review
```

If a specific label was given, filter accordingly. Resolve the type from the handoff first; if
no handoff exists, probe both `challenge show --label=<L>` and `bug show --label=<L>` to find
the matching task. Throughout the rest of the command, branch on type so you call
`crucible challenge ...` for challenges and `crucible bug ...` for bugs — never mix.

If nothing is in `review` for either type, report and stop.

### 2c. Verify branch existence

For each review task, confirm the local branch exists:

```bash
git rev-parse --verify challenge/<label> 2>/dev/null  # for challenges
git rev-parse --verify bug/<label> 2>/dev/null        # for bugs
```

If a handoff lists a combined-branch (e.g. `challenge/saga-canvas-overhaul`), verify that
branch instead. If a branch is missing, warn the user and exclude it from finalization — it may
exist in a different clone or have been cleaned up.

### 2d. Sync remote

```bash
git fetch origin main
```

### 2e. Detect fix commits

During `/phoe:execute`, the review phase (steps 4e–4f) may apply fix or suggestion-triage commits directly to local `main`. These are commits on `main` that no challenge or bug branch contains.

```bash
ORIGIN_MAIN=$(git rev-parse origin/main)
LOCAL_MAIN=$(git rev-parse main)

# Skip detection if local main equals origin/main (no execute-phase merges)
if [ "$ORIGIN_MAIN" = "$LOCAL_MAIN" ]; then
    FIX_COMMITS=0
else
    WORK_BRANCHES=$(git branch --list 'challenge/*' 'bug/*' --format='%(refname:short)' | tr '\n' ' ')
    FIX_COMMITS=$(git log --oneline origin/main..main --not $WORK_BRANCHES | wc -l)
fi
```

Record the count. If non-zero, the work branches alone do not represent the full reviewed state — this constrains the strategy options.

### 2f. Classify branch topology

For each work branch (a challenge or bug task), determine its relationship to `origin/main`:

```bash
ORIGIN_MAIN=$(git rev-parse origin/main)
MERGE_BASE=$(git merge-base $ORIGIN_MAIN <branch>)

if [ "$MERGE_BASE" = "$ORIGIN_MAIN" ]; then
    echo "INDEPENDENT"
else
    echo "DEPENDENT (branched from post-merge main)"
fi
```

For dependent branches, identify which other work branches are ancestors:

```bash
for other in $WORK_BRANCHES; do
    if [ "$other" != "<branch>" ]; then
        if git merge-base --is-ancestor "$other" "<branch>" 2>/dev/null; then
            echo "  predecessor: $other"
        fi
    fi
done
```

Build a dependency graph: nodes are work branches, directed edges mean "A is ancestor of B."

### 2g. Group into finalization sets

Using the dependency graph, the handoff strategy hints from 2a, and saga membership, group work branches:

- **Independent set**: Branches with no dependency edges between them. Each can be a standalone PR against `main`.
- **Dependency chain**: A linear sequence A → B → C where each depends on its predecessor. Typically a saga executed in order.
- **Combined branch**: A single branch carrying multiple challenges (declared by an `/phoe:execute` handoff with `Strategy: combined-branch`). Treat as one PR; do not try to split.
- **Mixed**: Some independent, some chained. Handle each group by its type.

Bugs are always one branch per task — they have no saga and no combined-branch strategy. Group them as independent unless a manual sequence has produced dependent bug branches.

### 2h. Check saga membership

For each challenge, check if it belongs to a saga:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json saga list
```

Saga membership informs the strategy recommendation — saga challenges are naturally grouped. Bugs do not have sagas; skip this for bug branches.

## 3. Recommend Strategy

Present the assessment and a strategy recommendation. **Always wait for the user's choice before executing.**

### Assessment format

```
Finalization Assessment
======================

Review challenges: 3
  challenge/add-viewport-resize  (independent)
  challenge/wire-canvas-events   (depends on: add-viewport-resize)
  challenge/polish-canvas-api    (depends on: wire-canvas-events)

Saga: canvas-overhaul (positions 2, 3, 4 of 6)
Fix commits on local main: 0
Local main ahead of origin/main by: 8 commits
```

### Strategy options

Evaluate and present the applicable options from the following. Not all options apply to every topology — only present options that make sense for the detected state.

#### Option: Individual PRs

Applicable when: all challenge branches are independent (no dependencies, no fix commits).

Push each `challenge/<label>` branch and create one PR per challenge against `main`.

- Pro: Clean diffs, individually reviewable, independently revertable
- Con: More PRs to manage, more merge cycles

#### Option: Stacked PRs

Applicable when: challenges form a dependency chain, no fix commits.

Push all branches. Create PRs with base-branch targeting so each PR shows only its own delta:

- First in chain: `--base main`
- Subsequent: `--base challenge/<predecessor-label>`

As each merges, GitHub auto-retargets the next PR to `main`.

- Pro: Each PR shows only its changes, preserves individual review
- Con: Must merge in strict order; squash-merge can cause auto-retarget issues (GitHub recreates the diff against `main` after predecessor squash-merges, which may show unexpected changes — rebasing the next branch onto updated `main` after each merge resolves this)

#### Option: Combined PR

Applicable when: challenges form a dependency chain (especially a saga), or when fix commits are present.

Create a single PR that encompasses all challenges. The branch to push depends on the topology:

- **No fix commits**: Push the last challenge branch in the chain (it includes all predecessors)
- **Fix commits present**: Create a `land/<saga-label>` or `land/<batch-name>` branch from local `main`, which includes both challenge commits and fix commits

One PR, one review cycle, one merge.

- Pro: Simplest merge path, automatically includes fix commits, one review
- Con: Larger diff, cannot revert individual challenges, harder to review

#### Option: Reconcile then stack

Applicable when: fix commits exist but the user wants individual PRs.

Cherry-pick fix commits from `main` onto their respective challenge branches, then follow the stacked PR strategy. Identify which fix commits belong to which challenge by their position in main's history (between a challenge's merge point and the next challenge's branch point).

- Pro: Individual PRs that include their review fixes
- Con: Cherry-pick may conflict, more complex, requires careful ordering

### Recommendation logic

Apply this decision tree:

1. Fix commits present AND >0 → **strongly recommend Combined PR** (reconcile-then-stack as alternative)
2. All independent, ≤5 challenges → **recommend Individual PRs**
3. Dependency chain, ≤3 challenges → **recommend Stacked PRs**
4. Dependency chain, >3 challenges → **recommend Combined PR** (stacked as alternative)
5. Mixed topology → **recommend Hybrid** (individual PRs for independents, combined for chains)

### Presentation

End the recommendation with a clear prompt:

```
Recommended: Combined PR (saga with 3 dependent challenges)
  → land/canvas-overhaul branch from challenge/polish-canvas-api
  → PR against main

Alternatives:
  • Stacked PRs (3 PRs, merge in order)
  • Individual PRs (not recommended — dependent branches, diffs overlap)

Which strategy?
```

## 4. Execute Chosen Strategy

After the user chooses, execute accordingly.

### 4a. Create finalization branches (if needed)

For combined PRs where fix commits require using local main:

```bash
git checkout -b land/<name> main
git push -u origin land/<name>
```

For combined PRs without fix commits, push the branch declared by the handoff (or the last branch in the dependency chain when there is no handoff):

```bash
git push -u origin <branch-name>
```

For individual or stacked PRs (challenge or bug):

```bash
git push -u origin challenge/<label>   # or bug/<label>
```

### 4b. Create PRs

Follow the project's PR format — summary and Crucible reference only, no test plan section.

**Individual or stacked PRs:**

```bash
gh pr create \
  --head <type>/<label> \
  --base <target> \
  --title "<task title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points: what changed and why>

Crucible: <label>
EOF
)"
```

`<type>` is `challenge` or `bug`. For stacked PRs (challenges only), `<target>` is `challenge/<predecessor-label>` for dependent challenges, `main` for the first. Bugs always target `main`.

**Combined PR:**

```bash
gh pr create \
  --head <branch-name> \
  --base main \
  --title "<saga name or descriptive batch title>" \
  --body "$(cat <<'EOF'
## Summary
<bullet points covering all tasks in the set>

Crucible: <label-1>, <label-2>, <label-3>
EOF
)"
```

Compose the summary from the handoff (if present) plus each task's title and key changes. Keep it concise — the individual specs in Crucible are the detailed record.

### 4c. Report

```
PRs Created
===========

| PR | Tasks | URL | Base |
|----|-------|-----|------|
| #42 | challenge/add-viewport-resize | https://github.com/.../pull/42 | main |
| #43 | challenge/wire-canvas-events  | https://github.com/.../pull/43 | challenge/add-viewport-resize |
| #44 | challenge/polish-canvas-api   | https://github.com/.../pull/44 | challenge/wire-canvas-events |
| #45 | bug/windows-focus-loss        | https://github.com/.../pull/45 | main |

Merge order: #42 → #43 → #44 (stacked — merge in sequence); #45 independent

After each merge, report back or run:
  /phoe:finalize landed <label>
```

For combined:

```
PR Created
==========

| PR | Tasks | URL |
|----|-------|-----|
| #42 | add-viewport-resize, wire-canvas-events, polish-canvas-api | https://github.com/.../pull/42 |

After merge, run:
  /phoe:finalize landed add-viewport-resize wire-canvas-events polish-canvas-api
```

## 5. Address PR Review Comments

After PRs are created, the user (or reviewers) may leave comments requesting changes. When the user relays review feedback or asks to address PR comments:

### 5a. Read the feedback

If the user provides a PR URL or number:

```bash
gh pr view <number> --comments
gh api repos/<owner>/<repo>/pulls/<number>/comments
```

Parse the review comments to understand what needs to change.

### 5b. Make fixes

Check out the relevant branch and apply the requested changes:

```bash
git checkout <type>/<label>   # challenge/<label> or bug/<label>
```

Apply fixes directly. These are typically small, targeted changes — the implementation was already reviewed and verified by the implementing agent.

If the fix introduces or modifies TODO comments, follow the discipline in the plugin's CLAUDE.md "TODO Comments" section: short, describe the work itself, no stale references (file paths, line numbers, labels, PR numbers, branch names).

### 5c. Rebuild

After making changes, rebuild to confirm the fix compiles:

```bash
/phoe:build
```

Only run the full `/phoe:verify` suite if the changes are significant (new logic, API changes, new files). For cosmetic fixes, naming changes, comment updates, or minor adjustments, a successful build is sufficient.

### 5d. Commit and push

```bash
git add <changed-files>
git commit -m "Address review: <brief description of what changed>"
git push origin <type>/<label>
```

The PR updates automatically. Do not reply to individual inline review comments — the fix commit is the response.

### 5e. Repeat

If further rounds of review comments arrive, repeat 5a–5d. Each round is a new commit on the branch.

## 6. Post-merge Tracking

Invoked as `/phoe:finalize landed <label> [<label2> ...]` (or the legacy alias `merged`), or when the user reports a PR was merged during conversation.

### 6a. Sync remote

```bash
git fetch origin main
git checkout main
git pull --ff-only origin main
```

If fast-forward fails (local main diverged from execute-phase merges), use:

```bash
git pull --rebase origin main
```

### 6b. Resolve task types

For each label, determine whether it is a challenge or a bug. First check the handoff in
`.claude/handoffs/finalize/` (the `Task type` field). If no handoff exists, probe both:

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
build-crucible-${PHOE_ENV}-release/bin/crucible challenge show --label=<LABEL> 2>/dev/null
build-crucible-${PHOE_ENV}-release/bin/crucible bug show --label=<LABEL> 2>/dev/null
```

Use whichever returns a record. The branch prefix (`challenge/` vs `bug/`) is the secondary
signal — they should agree.

### 6c. Verify merge landed

For each label, check that the work is on remote main, using the resolved branch name (`challenge/<label>` or `bug/<label>`):

```bash
# Signal A — branch tip is ancestor of origin/main (merge-commit style)
git merge-base --is-ancestor <type>/<label> origin/main 2>/dev/null && echo "confirmed via ancestry"

# Signal B — commit message references the label (squash-merge style)
git log origin/main --oneline -i --grep="<label>" -5
```

If neither signal confirms, tell the user and ask for explicit confirmation before proceeding. Do not auto-mark.

### 6d. Update Crucible

Use the type-correct terminal status:

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}

# Challenge
build-crucible-${PHOE_ENV}-release/bin/crucible challenge move --label=<LABEL> merged

# Bug
build-crucible-${PHOE_ENV}-release/bin/crucible bug move --label=<LABEL> done
```

### 6e. Clean up branches and handoffs

```bash
# Remote branch (use challenge/ or bug/ as appropriate)
git push origin --delete <type>/<label> 2>/dev/null || true

# Local branch
git branch -D <type>/<label>

# Associated worktree (if still present)
git worktree remove .claude/worktrees/<type>-<label> 2>/dev/null || true

# Handoff file (it's served its purpose)
rm -f .claude/handoffs/finalize/<type>-<label>.md
```

For combined PRs, also clean the finalization branch and any combined-branch handoff:

```bash
git push origin --delete land/<name> 2>/dev/null || true
git branch -D land/<name> 2>/dev/null || true
rm -f .claude/handoffs/finalize/<combined-branch-suffix>.md
```

After deletions, prune empty handoff state:

```bash
rmdir .claude/handoffs/finalize 2>/dev/null || true
```

### 6f. Report

Show what was marked and saga progress (challenges only — bugs have no saga):

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json saga show --label=<SAGA_LABEL>
```

```
Finalized
=========

| Task                | Type      | Status | Cleaned |
|---------------------|-----------|--------|---------|
| add-viewport-resize | challenge | merged | branch deleted |
| wire-canvas-events  | challenge | merged | branch deleted |
| windows-focus-loss  | bug       | done   | branch deleted |

Saga: canvas-overhaul — 4/6 complete (was 2/6)

Remaining:
  challenge/polish-canvas-api — PR #44 (awaiting merge)
  2 challenges still in todo
```

### 6g. Stacked PR maintenance

For stacked PRs, after merging one PR the next in the stack may need attention:

- **Merge-commit strategy on remote**: GitHub auto-retargets the next PR. No action needed.
- **Squash-merge strategy on remote**: The next PR's base branch was deleted. GitHub retargets to `main` but the diff may show already-merged commits. Rebase the next branch:

```bash
git checkout challenge/<next-label>
git rebase origin/main
git push --force-with-lease origin challenge/<next-label>
```

Detect which case applies by checking after the merge whether the next PR's diff is clean:

```bash
gh pr view <next-pr-number> --json additions,deletions
```

If the diff is unexpectedly large (significantly more additions/deletions than the challenge's scope), the squash-merge retarget issue likely occurred. Offer to rebase.

## 7. Workspace Reconciliation

After all tasks from a finalization session are merged, local `main` may still carry the execute-phase merges and diverge from `origin/main`. Remind the user:

```
All tasks finalized. Local main may be out of sync with remote.
Run /phoe:reset-workspace to reconcile.
```

Do not reset local `main` directly — defer to `/phoe:reset-workspace` which handles this safely with user confirmation.
