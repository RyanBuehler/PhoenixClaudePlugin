# Parallel integration and dependent PRs

## Capability investigation — 2026-10-08

GitHub documents native stacks with a shared trunk, stack-aware checks, ordered landing and
automatic rebasing of remaining layers after bottom-layer landing. Same-repository branches are
required; cross-fork stacks are unsupported. See [stack rules](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests).
Phoenix currently allows squash, merge and rebase merges; do not assume parent commit identity
survives landing. Check live repository settings before choosing a method.

The official `github/gh-stack` extension provides stack operations; it is an extension, not a
built-in `gh pr` subcommand. The installed v0.1.0 help confirms `push` uses per-branch
force-with-lease and may partially succeed, while `sync` rebases and pushes with leases atomically.
Those commands rewrite published history. Consult the current session's push/history policy;
if rewrites are prohibited or unapproved, use the replacement-branch fallback below. Do not hide
a force push inside an extension command. See [extension commands](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands).

Recommendation: independent work uses main-base PRs; tightly coupled small work uses one combined
PR. Dependent work can use a **native GitHub stack** when the capability is confirmed on the actual
repository, linear history can be maintained, and its updates comply with policy. Otherwise wait
for the predecessor to land, or use a draft dependency PR with the explicit fallback below.
Plain branch-targeted PRs are not automatically a native stack: confirm the stack map/identity.
See [creation and conversion](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests).

## Native stack lifecycle

1. Keep normal named, dedicated worktrees. Record trunk, ordered PR URLs, head branches/SHAs,
   predecessor PR and the exact parent SHA included in each child's history. Verify ancestry
   (`git merge-base --is-ancestor <parent-sha> <child-sha>`); preserve the child-only range.
2. Check credentials and push permission per CLAUDE.md. Publish each branch normally and open
   the bottom PR against main, dependent PRs against their predecessor, initially draft.
   `gh pr create --base <parent-branch> --head <child-branch> --draft --body-file <file>` is
   supported. Record dependencies and child range in the body.
3. If the installed extension supports it, `gh stack link <bottom-pr-url> <child-pr-url>` links
   existing PRs in bottom-to-top order without adopting local tracking. Prefer PR URLs over
   branch arguments: branch arguments can push/create PRs implicitly. Confirm the resulting
   stack map and trunk on GitHub. If unavailable, keep the child draft and use the fallback.
4. Parent changes can invalidate the child and its tests. Coordinate all worktree owners before
   any cascading operation. Use `gh stack rebase`/`gh stack push` or `gh stack sync` only when
   history rewrites are authorized, every affected worktree is quiescent and the installed help
   matches the documented operation. Otherwise replace the child branch/PR; do not ordinary-rebase
   a published child or force-push it as an implicit repair. Re-verify every changed layer.
5. Leave merging to the owner. Immediately before presenting a layer as ready, fetch and inspect
   `gh pr view <url> --json state,baseRefName,headRefName,headRefOid,mergeCommit` for it and its
   predecessor. Confirm the native stack still has the intended trunk/order. After a predecessor
   lands, prove `state=MERGED` and `git merge-base --is-ancestor <merge-sha> origin/main`.
   Observe the automatic server rebase/base update; do not assume it occurred. Fetch updated
   heads, inspect child-only diff and re-verify. Fast-forward a local branch only if possible;
   if the remote was rewritten, preserve local work and use a fresh worktree on the fetched head.
6. An ordinary dependency PR must target main before it becomes ready after parent landing.
   A native child is ready only while its verified stack identity ensures landing on the trunk.
   If the parent landed into another branch, the stack disappeared, or the base is stale, keep
   the child draft and repair it. Do not merge a child into an abandoned parent branch. State
   can race: re-read it at the readiness boundary; if landing happened during recovery, fetch
   and inspect actual main contents before publishing a replacement. Never apply the child twice.

## Squash-safe fallback without rewriting published history

For a non-native dependency PR after a parent squash merge, retargeting alone does not remove the
old parent commits. An ordinary `rebase origin/main` can replay them. Freeze child HEAD and its
recorded included-parent SHA; confirm that SHA is an ancestor. Save the exact child-only patch:

```bash
git diff --binary <included-parent-sha> <child-sha> > /tmp/child-only.patch
git worktree add .claude/worktrees/challenge-<replacement-label> \
  -b challenge/<replacement-label> origin/main
```

In the replacement worktree, `git apply --3way --index /tmp/child-only.patch` applies only child
work. Inspect conflicts against current main; never take a whole parent snapshot as resolution.
If the range contains unrelated commits or the included-parent SHA is unknown, stop and recover
the boundary before applying. Reconcile semantic overlap, verify, commit and publish a replacement
PR against main. Compare its diff with the frozen child-only intent, and link the old PR/range.
Close the superseded PR only after the replacement is created and checked. Preserve the old
branch while any dependent PR targets it. A new branch avoids any rewrite of the old remote.

If the old child raced and landed, first prove reachability and inspect which child changes are
already on main. No missing child diff means no replacement; otherwise recover only missing intent
in a new main-base PR. A MERGED badge without main reachability is not proof of landing.

## Independent siblings and semantic overlap

Before dispatch and again after integrating current main, compare sibling changed files and the
shared producers/consumers they imply: stage lists/counts, recipes, public signatures, generated
fixtures and metadata. Disjoint file lists can still share a contract. Assign one integration
owner for overlap; serialize or combine work when ownership cannot be separated.

After a clean merge/rebase, inspect the integrated contract, regenerate through its producer,
and recompute derived values from the complete list. If siblings each add a stage to an N-stage
pipeline, the result must contain both stages in the intended order and count N+2, even if both
branches independently changed N to N+1 without a text conflict. Check call sites against updated
signatures, recipe dependencies and fixture output, then verify affected profiles. Record sibling
ranges, overlap, resulting count/order and verification. A text-clean integration is not evidence
of semantic correctness. These gates apply before both execute integration rebases and publish.
