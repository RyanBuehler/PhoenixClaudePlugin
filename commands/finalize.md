---
description: Finalize completed challenges into remote main via PR — analyzes branch topology, recommends PR strategy, pushes, creates PRs, addresses review feedback, and tracks post-merge Crucible status.
---

Finalize completed Crucible challenges into remote main. Analyzes branch topology from a `/phoe:execute` run (or manual `/phoe:implement` sessions), recommends a PR strategy, creates PRs after user approval, addresses PR review comments, and tracks post-merge status updates.

> **Verification is the implementing agent's responsibility.** Challenges arriving in `review` status have already passed `/phoe:verify` (build + format + lint + test). This command does not re-run the full verification suite. When addressing PR review comments, rebuild to confirm the fix compiles. Only re-run `/phoe:verify` if the changes are significant enough to warrant it (e.g., logic changes, new files, API modifications).

## Arguments

- *(no argument)* — assess all `review`-status challenges and recommend a finalization strategy
- **`<label>`** — finalize a specific challenge
- **`merged <label> [<label2> ...]`** — mark one or more challenges as merged after their PR lands on remote main

Determine which mode by checking if the first word is `merged` (post-merge tracking), otherwise treat as assessment/finalization mode.

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

### 2a. Gather review challenges

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json challenge list --status=review
```

If a specific label was given, filter to just that challenge. If no challenges are in `review`, report and stop.

### 2b. Verify branch existence

For each review challenge, confirm the local branch exists:

```bash
git rev-parse --verify challenge/<label> 2>/dev/null
```

If a branch is missing, warn the user and exclude it from finalization — it may exist in a different clone or have been cleaned up.

### 2c. Sync remote

```bash
git fetch origin main
```

### 2d. Detect fix commits

During `/phoe:execute`, the review phase (steps 4e–4f) may apply fix or suggestion-triage commits directly to local `main`. These are commits on `main` that no challenge branch contains.

```bash
ORIGIN_MAIN=$(git rev-parse origin/main)
LOCAL_MAIN=$(git rev-parse main)

# Skip detection if local main equals origin/main (no execute-phase merges)
if [ "$ORIGIN_MAIN" = "$LOCAL_MAIN" ]; then
    FIX_COMMITS=0
else
    CHALLENGE_BRANCHES=$(git branch --list 'challenge/*' --format='%(refname:short)' | tr '\n' ' ')
    FIX_COMMITS=$(git log --oneline origin/main..main --not $CHALLENGE_BRANCHES | wc -l)
fi
```

Record the count. If non-zero, the challenge branches alone do not represent the full reviewed state — this constrains the strategy options.

### 2e. Classify branch topology

For each challenge branch, determine its relationship to `origin/main`:

```bash
ORIGIN_MAIN=$(git rev-parse origin/main)
MERGE_BASE=$(git merge-base $ORIGIN_MAIN challenge/<label>)

if [ "$MERGE_BASE" = "$ORIGIN_MAIN" ]; then
    echo "INDEPENDENT"
else
    echo "DEPENDENT (branched from post-merge main)"
fi
```

For dependent branches, identify which challenge branches are ancestors:

```bash
for other in $CHALLENGE_BRANCHES; do
    if [ "$other" != "challenge/<label>" ]; then
        if git merge-base --is-ancestor "$other" "challenge/<label>" 2>/dev/null; then
            echo "  predecessor: $other"
        fi
    fi
done
```

Build a dependency graph: nodes are challenges, directed edges mean "A is ancestor of B."

### 2f. Group into finalization sets

Using the dependency graph and saga membership, group challenges:

- **Independent set**: Challenges with no dependency edges between them. Each can be a standalone PR against `main`.
- **Dependency chain**: A linear sequence A → B → C where each depends on its predecessor. Typically a saga executed in order.
- **Mixed**: Some independent, some chained. Handle each group by its type.

### 2g. Check saga membership

For each challenge, check if it belongs to a saga:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json saga list
```

Saga membership informs the strategy recommendation — saga challenges are naturally grouped.

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

For combined PRs without fix commits, using the last challenge branch:

```bash
git push -u origin challenge/<last-in-chain>
```

For individual or stacked PRs:

```bash
git push -u origin challenge/<label>
```

### 4b. Create PRs

Follow the project's PR format — summary and Crucible reference only, no test plan section.

**Individual or stacked PRs:**

```bash
gh pr create \
  --head challenge/<label> \
  --base <target> \
  --title "<challenge title>" \
  --body "$(cat <<'EOF'
## Summary
<2-4 bullet points: what changed and why>

Crucible: <label>
EOF
)"
```

For stacked PRs, `<target>` is `challenge/<predecessor-label>` for dependent challenges, `main` for the first.

**Combined PR:**

```bash
gh pr create \
  --head <branch-name> \
  --base main \
  --title "<saga name or descriptive batch title>" \
  --body "$(cat <<'EOF'
## Summary
<bullet points covering all challenges in the set>

Crucible: <label-1>, <label-2>, <label-3>
EOF
)"
```

Compose the summary from each challenge's title and key changes. Keep it concise — the individual challenge specs in Crucible are the detailed record.

### 4c. Report

```
PRs Created
===========

| PR | Challenge(s) | URL | Base |
|----|-------------|-----|------|
| #42 | add-viewport-resize | https://github.com/.../pull/42 | main |
| #43 | wire-canvas-events | https://github.com/.../pull/43 | challenge/add-viewport-resize |
| #44 | polish-canvas-api | https://github.com/.../pull/44 | challenge/wire-canvas-events |

Merge order: #42 → #43 → #44 (stacked — merge in sequence)

After each merge, report back or run:
  /phoe:finalize merged <label>
```

For combined:

```
PR Created
==========

| PR | Challenge(s) | URL |
|----|-------------|-----|
| #42 | add-viewport-resize, wire-canvas-events, polish-canvas-api | https://github.com/.../pull/42 |

After merge, run:
  /phoe:finalize merged add-viewport-resize wire-canvas-events polish-canvas-api
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
git checkout challenge/<label>
```

Apply fixes directly. These are typically small, targeted changes — the implementation was already reviewed and verified by the implementing agent.

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
git push origin challenge/<label>
```

The PR updates automatically. Do not reply to individual inline review comments — the fix commit is the response.

### 5e. Repeat

If further rounds of review comments arrive, repeat 5a–5d. Each round is a new commit on the branch.

## 6. Post-merge Tracking

Invoked as `/phoe:finalize merged <label> [<label2> ...]` or when the user reports a PR was merged during conversation.

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

### 6b. Verify merge landed

For each label, check that the challenge's work is on remote main:

```bash
# Signal A — branch tip is ancestor of origin/main (merge-commit style)
git merge-base --is-ancestor challenge/<label> origin/main 2>/dev/null && echo "confirmed via ancestry"

# Signal B — commit message references the label (squash-merge style)
git log origin/main --oneline -i --grep="<label>" -5
```

If neither signal confirms, tell the user and ask for explicit confirmation before proceeding. Do not auto-mark.

### 6c. Update Crucible

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
build-crucible-${PHOE_ENV}-release/bin/crucible challenge move --label=<LABEL> merged
```

### 6d. Clean up branches

```bash
# Remote branch
git push origin --delete challenge/<label> 2>/dev/null || true

# Local branch
git branch -D challenge/<label>

# Associated worktree (if still present)
git worktree remove .claude/worktrees/challenge-<label> 2>/dev/null || true
```

For combined PRs, also clean the finalization branch:

```bash
git push origin --delete land/<name> 2>/dev/null || true
git branch -D land/<name> 2>/dev/null || true
```

### 6e. Report

Show what was marked and saga progress:

```bash
build-crucible-${PHOE_ENV}-release/bin/crucible --json saga show --label=<SAGA_LABEL>
```

```
Finalized
=========

| Challenge | Status | Cleaned |
|-----------|--------|---------|
| add-viewport-resize | merged | branch deleted |
| wire-canvas-events  | merged | branch deleted |

Saga: canvas-overhaul — 4/6 complete (was 2/6)

Remaining:
  challenge/polish-canvas-api — PR #44 (awaiting merge)
  2 challenges still in todo
```

### 6f. Stacked PR maintenance

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

After all challenges from a finalization session are merged, local `main` may still carry the execute-phase merges and diverge from `origin/main`. Remind the user:

```
All challenges finalized. Local main may be out of sync with remote.
Run /phoe:reset-workspace to reconcile.
```

Do not reset local `main` directly — defer to `/phoe:reset-workspace` which handles this safely with user confirmation.
