---
description: Remove worktrees whose branch has provably landed on origin/main — dry-run first, PR-confirmed, with every skipped tree given a reason.
allowed-tools: Read, Bash, Glob, Grep
disable-model-invocation: true
---

Collect the worktrees under `.claude/worktrees/` whose work has landed, and leave everything
else alone. Background sessions and `isolation: worktree` sub-agents accumulate hundreds of
these; each carries its own Forge build tree, so the directory reaches hundreds of gigabytes.

The whole command is `scripts/gc_worktrees.py`. Classification is deterministic and lives in the
script, not in your judgment — do not hand-pick worktrees to delete, and do not `rm -rf`
`.claude/worktrees/` or any entry under it.

## Arguments

- *(no argument)* — dry run. Print the verdict for every worktree and delete nothing.
- **`apply`** — remove the worktrees the dry run marked `REMOVE`, and delete their landed branches.

## 1. Dry Run

Always run this first, from the main checkout:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gc_worktrees.py --repo <main-checkout>
```

It fetches with `--prune`, then prints one line per worktree: `REMOVE` or `keep`, the branch, and
the reason. Show the user the summary line and the reason breakdown, not all 100+ rows.

## 2. What Counts as Landed

A worktree is removable only when its branch is proven landed **and** no guard fires. The two
proofs, strongest first:

| Reason | Evidence |
|---|---|
| `landed: merged into origin/main` | The branch is an ancestor of `origin/main`. Cryptographic; needs no network. |
| `landed: PR #N merged` | GitHub reports a merged pull request for this branch head. |

**A deleted remote branch is not proof.** Closing a pull request unmerged deletes the branch too,
and a branch pushed without an upstream never had one. Such a worktree is kept with
`upstream gone but no merged PR — review by hand`. On the first real sweep this held back four
worktrees carrying 1, 4, 9, and 9 unique commits — one of them PR #2689, closed unmerged.

`--trust-gone` downgrades that to `landed: upstream gone (unverified)` and makes it removable.
Do not pass it to clear a backlog; it exists for a repository with no GitHub remote, and it
deletes exactly the work the guard above saved.

If `gh` cannot answer, the script warns on stderr and keeps every gone-upstream worktree. An
unreachable GitHub means *cannot verify*, never *not merged* — do not paper over that warning.

## 3. Guards

A landed worktree is still kept when any of these holds. Each is reported by name, so a kept tree
is never a silent skip:

- **`locked`** — someone marked it with `git worktree lock`.
- **`in use by pid N`** — a live process has its cwd inside the tree. This is what protects a
  running background session from having its checkout deleted underneath it.
- **`build lock held`** — a `forge.lock` exists under `Applications/Forge/`. A killed build leaves
  one for up to two hours; removing the tree under a live builder strands it mid-write.
- **`N uncommitted change(s)`** — `git status --porcelain` is non-empty. Ignored build output does
  not count, so a `.forge` tree never pins a landed worktree.
- **`detached HEAD`** — no branch, so nothing can be proven about it.
- **`N commit(s) not on origin/main`** — the ordinary in-flight case.

## 4. Apply

Report the dry-run summary and get the user's go-ahead before this step. Deletion is not
reversible from here: the branch goes too, and a worktree's build tree is not recoverable.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gc_worktrees.py --repo <main-checkout> --apply
```

Useful flags:

- `--limit N` — act on at most N. Use it to prove the removal path before a large sweep.
- `--keep-branches` — remove the worktree, leave the landed branch.
- `--sizes` — measure disk per candidate, so the report can state what was reclaimed. Slow.
- `--json` — machine-readable output.

Removal uses `git worktree remove` without `--force`, so a tree that turned dirty between
classification and deletion is refused rather than destroyed. Failures are reported per path and
the command exits non-zero; do not retry one with `--force` by hand.

Afterwards the script runs `git worktree prune`. Report what was removed, what was reclaimed, and
every `review by hand` entry — those need a human.

## 5. Refusals

The script exits 2 rather than guess when:

- `--repo` points inside a worktree instead of the main checkout. Worktrees share one worktree
  list, and a sweep launched from a member would target its own siblings.
- The upstream ref does not exist.
- `git fetch --prune` fails, which would leave every upstream verdict stale.

Do not work around a refusal — fix the input.
