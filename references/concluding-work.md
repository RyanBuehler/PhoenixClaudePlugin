# Concluding work: worktree, local branch, remote branch

The repository does not delete a head branch on merge, so a pushed branch stays on `origin` until
something deletes it. The agent that sees its own branch land deletes all three artifacts.

## Landing is proven, never inferred

A branch has landed when its PR's `state` is `MERGED` **and** the merge commit is reachable from
`origin/main`:

```bash
git fetch origin main
git merge-base --is-ancestor <merge-sha> origin/main
```

An open PR, a PR closed unmerged, or a remote branch that has merely vanished is not landing —
leave every artifact in place and say so in the report.

## Between pushing and landing

Remove only the worktree. The local and remote branches carry the open PR; make review fixes from
a fresh worktree on the same branch.

## Once landed

From the main checkout, skipping any step whose artifact is already gone:

```bash
git worktree remove .claude/worktrees/<type>-<label>   # never --force; a refusal means uncommitted work
git branch -D <type>/<label>                           # -D: a squash merge is not an ancestor, so -d refuses
git push origin --delete <type>/<label>
git fetch --prune origin
```

- If the session entered the worktree with `EnterWorktree(path=...)`, call `ExitWorktree(keep)`
  first — entering by path takes no removal ownership, and removing the tree you stand in leaves
  the session pinned to a missing directory.
- Delete only the branch this work created. Keep a landed branch that another open PR targets
  (`gh pr list --base <type>/<label>`) until that PR is retargeted.
- Report what was removed and anything kept, with the reason.

`/phoe:gc-worktrees` sweeps many landed worktrees at once; its `landed` verdict is the same proof.
