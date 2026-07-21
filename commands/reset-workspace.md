---
description: Clean up the workspace — resolve unstaged files, switch to main, pull latest, and prune stale local branches.
allowed-tools: Read, Bash, Glob, Grep, Agent
disable-model-invocation: true
---

Clean up the current workspace by working through these steps in order. Each step involves investigation before action — confirm with the user before anything destructive.

## Arguments

- *(no argument)* — clean git state only (unstaged files, branches, worktrees). Leave `build-*/` directories untouched so subsequent builds stay incremental.
- **`all`** — additionally wipe top-level `build-*/` directories. Use after toolchain swaps, branch churn that produced stale CMake caches, or before disk-space cleanup.

Treat any argument other than the literal `all` as no argument (do not invent partial modes).

## 1. Investigate Unstaged and Untracked Files

Run `git status` to see the current state. If there are:

- **Modified tracked files**: Show the user what changed (use `git diff --stat` for a summary). Ask whether to:
  - Stash them (`git stash push -m "reset-workspace: stashed changes"`)
  - Discard them (`git checkout -- <files>`)
  - Leave them (abort cleanup)
- **Untracked files**: Show the list. Ask whether to:
  - Delete them (`git clean -fd` for directories, `git clean -f` for files — but **never** clean files matching `.env`, `.local`, `*.cfg`, or build directories without explicit confirmation)
  - Leave them

If the working tree is already clean, say so and move on.

## 2. Switch to Main

Before switching:
- Verify you are not in the middle of a merge, rebase, or cherry-pick (`git status` will indicate this). If so, warn the user and stop.
- Check the current branch name. If already on `main`, skip this step.

```bash
git checkout main
```

If the checkout fails (e.g., because of uncommitted changes that weren't handled in step 1), report the error and stop.

## 3. Update Main

Pull the latest changes:

```bash
git pull
```

Report whether new commits were pulled or main was already up to date.

## 4. Prune Stale Branches and Worktrees

Update remote tracking info:

```bash
git fetch --prune
```

Find local branches whose upstream is gone:

```bash
git branch -vv
git worktree list --porcelain
```

Look for branches marked `[gone]` in `git branch -vv` output. If any exist:
- List them for the user with their last commit message.
- For each gone branch that has an associated worktree under `.claude/worktrees/`, remove the worktree first: `git worktree remove .claude/worktrees/<type>-<label>`. A branch cannot be deleted while checked out in a worktree.
- Delete the branch with `git branch -D <branch>` — no confirmation needed since the remote is already gone (typically merged via PR).
- After processing all gone branches, run `git worktree prune` to clear administrative entries for directories the user manually removed.

Leave worktrees whose branch is still live in place — they represent blocked or in-progress work. Do not `rm -rf` `.claude/worktrees/`.

Also list any remaining local branches (excluding `main`) that still have a valid remote, so the user is aware of them — but do **not** delete these without being asked.

## 5. Clean Build Directories

**Skip this step entirely unless the user passed the `all` argument.** Build directories are
expensive to regenerate (~3–4 min per app for a cold build), and the default reset is meant to
preserve incremental build state. If no argument was passed, say "leaving build directories in
place — pass `all` to wipe them" and continue to step 6.

Forge writes all build output under `Applications/Forge/`: `.forge-out/` and `.forge/` hold the
per-profile build trees, and `.bootstrap-out/` holds the cold-start `forge` binary. These are
regeneratable artifacts and frequently go stale after branch switches or toolchain updates —
removing them forces a clean reconfigure (and re-bootstrap) on the next `/phoe:build` run.

List the candidates:

```bash
ls -d Applications/Forge/.forge-out Applications/Forge/.forge Applications/Forge/.bootstrap-out 2>/dev/null
```

If any exist:

- Show the list to the user with total disk size (`du -sh Applications/Forge/.forge-out Applications/Forge/.forge Applications/Forge/.bootstrap-out 2>/dev/null`).
- Warn that the next build in each profile will be a full cold build (~3–4 min per app) and that
  `forge` will re-bootstrap first.
- Ask for explicit confirmation before deleting.

On confirmation, wipe the build trees with Forge's own cleaner (which understands its layout), then
remove the bootstrap binary so it recompiles fresh:

```bash
Applications/Forge/.bootstrap-out/forge clean --all 2>/dev/null
rm -rf Applications/Forge/.forge-out Applications/Forge/.forge Applications/Forge/.bootstrap-out
```

Do **not** delete build output inside worktrees (`.claude/worktrees/*/Applications/Forge/.forge*`)
from this command — those belong to in-flight work and are cleaned when the worktree itself is
removed. Only touch the main repo's Forge output dirs.

If the working tree is a worktree itself (detect via `git rev-parse --is-inside-work-tree` plus
`git rev-parse --git-common-dir` differing from `.git`), refuse this step and tell the user to
run `/phoe:reset-workspace` from the main checkout — cleaning the main repo's build dirs from a
worktree is surprising and error-prone.

## 6. Report

Tell the user what was done:
- Files stashed/discarded/left
- Branch switched
- Commits pulled
- Branches pruned
- Build directories removed (only when invoked with `all`) or left in place
