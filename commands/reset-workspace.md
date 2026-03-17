---
description: Clean up the workspace — resolve unstaged files, switch to main, pull latest, and prune stale local branches.
allowed-tools: Read, Bash, Glob, Grep, Agent
---

Clean up the current workspace by working through these steps in order. Each step involves investigation before action — confirm with the user before anything destructive.

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

## 4. Prune Stale Branches

Update remote tracking info:

```bash
git fetch --prune
```

Find local branches whose upstream is gone:

```bash
git branch -vv
```

Look for branches marked `[gone]` in the output. If any exist:
- List them for the user with their last commit message
- Ask for confirmation before deleting
- Delete confirmed branches with `git branch -D <branch>`

Also list any remaining local branches (excluding `main`) that still have a valid remote, so the user is aware of them — but do **not** delete these without being asked.

## 5. Report

Tell the user what was done:
- Files stashed/discarded/left
- Branch switched
- Commits pulled
- Branches pruned
