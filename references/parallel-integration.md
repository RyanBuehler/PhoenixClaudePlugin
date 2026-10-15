# Parallel integration and dependent PRs

## Choosing a shape

- Independent work: one PR per branch, based on main.
- Tightly coupled small work: one combined PR.
- Dependent work: a stack of PRs, each based on its parent's branch, the layers above the bottom
  as drafts. The owner merges bottom-up with "Create a merge commit", never "Update branch", so a
  parent's commits keep their identity on main. The repository also allows squash and rebase merges,
  so check what actually happened before relying on that (§Squash-safe fallback).

**GitHub native stacks** add a shared trunk, stack-aware checks, ordered landing and automatic
rebasing of the remaining layers once the bottom lands. They need same-repository branches (no
forks), and a PR based on another branch is not one until the stack map confirms it
([stack rules](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests),
[creating stacks](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests)).
The `github/gh-stack` extension (not a built-in `gh pr` subcommand) provides the operations. Its
`push` uses per-branch force-with-lease and can partially succeed; `sync` rebases and pushes
atomically. Both rewrite published history, so use them only when the session's policy authorizes
rewrites; never hide a force push inside an extension command
([extension commands](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands)).

## Native stack lifecycle

1. Give every layer its own named worktree. Record the trunk, the ordered PR URLs, each head branch
   and SHA, its predecessor PR, and the exact parent SHA in each child's history. Check ancestry
   (`git merge-base --is-ancestor <parent-sha> <child-sha>`) and keep the child-only range.
2. Open the bottom PR against main and each child against its predecessor, as a draft:
   `gh pr create --base <parent-branch> --head <child-branch> --draft --body-file <file>`, with the
   dependency and child range in the body.
3. To make it a native stack, link the existing PRs bottom-to-top with
   `gh stack link <bottom-pr-url> <child-pr-url>` if the installed extension supports it. Pass PR
   URLs, not branches: branch arguments can push or create PRs implicitly. Confirm the stack map and
   trunk on GitHub. Without the extension, the child stays a draft dependency PR.
4. A parent change can invalidate the child and its trials. Coordinate every affected worktree's
   owner first. Carry the change up without rewriting: rebase a child only while it is unpushed;
   once pushed, merge the parent branch into it and push. `gh stack rebase`, `push` or `sync` only
   when rewrites are authorized, every affected worktree is quiescent, and the installed help
   matches the documented operation. Never force-push a child as a repair. Re-verify every changed
   layer.
5. Merging is the owner's. Immediately before presenting a layer as ready, inspect it and its
   predecessor with `gh pr view <url> --json state,baseRefName,headRefName,headRefOid,mergeCommit`,
   and confirm a native stack still has the intended trunk and order. After a predecessor lands,
   prove `state=MERGED` and `git merge-base --is-ancestor <merge-sha> origin/main`. Observe the
   server's rebase or base update rather than assuming it; fetch the updated heads, inspect the
   child-only diff and re-verify. Fast-forward a local branch only when possible; if the remote was
   rewritten, keep local work and use a fresh worktree on the fetched head.
6. An ordinary dependency PR is retargeted to main (`gh pr edit <N> --base main`) before it is
   marked ready. A native child is ready only while its verified stack identity lands it on the
   trunk. If the parent landed into another branch, the stack disappeared or the base is stale,
   keep the child a draft and repair it; never merge a child into an abandoned parent branch. State
   can race: re-read it at the readiness boundary, and if landing happened mid-recovery, inspect
   main's actual contents before publishing a replacement. Never apply the child twice.

## Squash-safe fallback without rewriting published history

After a parent squash merge, retargeting a non-native child does not remove the old parent commits,
and an ordinary `rebase origin/main` can replay them. Instead, freeze the child HEAD and its recorded
parent SHA, confirm that SHA is an ancestor, and save the child-only patch:

```bash
git diff --binary <included-parent-sha> <child-sha> > /tmp/child-only.patch
git worktree add .claude/worktrees/challenge-<replacement-branch-label> \
  -b challenge/<replacement-branch-label> origin/main
```

In the replacement worktree, `git apply --3way --index /tmp/child-only.patch` applies only the
child's work. Resolve conflicts against current main, never by taking a whole parent snapshot. If the
range holds unrelated commits or the parent SHA is unknown, stop and recover the boundary first.
Reconcile semantic overlap, verify, commit, and open a replacement PR against main; compare its diff
with the frozen child-only intent and link the old PR and range. Close the superseded PR only after
the replacement is created and checked, and keep the old branch while any PR targets it.

If the old child raced and landed, prove reachability first and inspect which child changes are
already on main. No missing child diff means no replacement; otherwise recover only the missing
intent in a new main-based PR. A MERGED badge without reachability from main is not landing.

## Independent siblings and semantic overlap

Before dispatch, and again after integrating current main, compare siblings' changed files and the
shared producers and consumers they imply: stage lists and counts, recipes, public signatures,
generated fixtures, metadata. Disjoint file lists can still share a contract. Give overlap one
integration owner; serialize or combine work whose ownership cannot be separated.

After a clean merge or rebase, inspect the integrated contract, regenerate through its producer, and
recompute derived values from the complete list. If two siblings each add a stage to an N-stage
pipeline, the result has both stages in the intended order and N+2 of them, even though each branch
changed N to N+1 without a text conflict. Check call sites against updated signatures, recipe
dependencies and fixture output, then verify the affected profiles. Record the sibling ranges, the
overlap, the resulting count and order, and the verification. A text-clean integration is not
evidence of semantic correctness. These gates apply before execute's integration rebases and before
publishing.
