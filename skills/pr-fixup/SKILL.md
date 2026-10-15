---
name: pr-fixup
description: Use when fixing an open PR — review feedback, merge conflicts or CI failures. Merges main, addresses comments, pushes, resolves threads, then builds locally while CI runs. Auto-activates on phrases like "address PR feedback", "fix the review comments", "handle PR review", "respond to reviewers".
---

# PR Fixup

A PR has new review comments, may have drifted from main, and needs another revision. The order is
fix, commit, push, resolve threads, then build while CI runs. A PR with only a merge conflict or a
CI failure runs steps 1, 4, 5 and 7 (read a CI failure with `gh run view <run-id> --log-failed`).

Work in the PR branch's worktree. If it was removed after publishing, add a fresh one on the
existing branch: `git worktree add .claude/worktrees/<type>-<label> <type>/<label>`.

## 1. Sync with main

```bash
git fetch origin main
git merge origin/main
```

A stacked PR (its base is another PR's branch) merges `origin/<base-branch>` instead. Never rebase
or force-push: published history is not rewritten here; if a rebase seems required, ask the user.

Resolve conflicts before anything else, investigating each rather than taking a side. Where a
conflict touches code a comment also cites, resolve the conflict first so the fix applies to the
merged state.

## 2. Pull review comments

```bash
gh pr view --comments
gh api repos/{owner}/{repo}/pulls/{number}/comments    # inline review comments
gh api repos/{owner}/{repo}/pulls/{number}/reviews     # review summaries
```

Collect every unresolved top-level and inline comment, with its thread ID (GraphQL
`pullRequest.reviewThreads`). Leave alone a thread the user reopened, unless told to re-resolve it.

## 3. Triage

- **Actionable:** a clear code change is requested.
- **Question:** needs an answer, not a change.
- **Disagreement:** conflicts with intent or another constraint; raise it with the user before
  acting.
- **Out of scope:** file a Crucible follow-up instead of growing the PR.

Every comment ends in one of two states: **fixed and resolved**, or **reply drafted and thread left
open** (questions, disagreements, out of scope, deferred actionables). Anything else is unfinished.

Before acting on an actionable comment, verify its code claim per the core rules (§Conduct,
review comments): line numbers drift across PR updates. If the cited
construct is not on or near that line, ask the reviewer instead of guessing.

## 4. Fix and commit

Make the requested changes one comment at a time, scoped to the ask; a fixup is not a refactor.
Commit them. Draft a reply for every other comment (the answer, the rationale, or the follow-up's
label); drafts stay local for the user to post.

## 5. Push

Push as soon as the fixes are committed, so CI starts now:

```bash
git diff --check origin/main...HEAD   # catches leftover conflict markers
git push
```

Do not batch unrelated work into the push; each extra commit delays CI.

## 6. Resolve threads

Resolve a thread only once a pushed commit addresses its ask; check the diff first, never resolve
speculatively, and never resolve a question, disagreement or out-of-scope thread.

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { isResolved }
    }
  }' -f threadId="<thread-id>"
```

Then audit: every actionable thread resolved with a fix, every other thread open with a drafted
reply.

## 7. Build while CI runs

Check load first: this box is also a CI runner, so if a CI job or another build is running here,
skip the build and let CI be the build. Otherwise run `/phoe:build` for the relevant profile. Do
not run `/phoe:verify`; that gate is the user's. If the build fails, fix, commit and push again.

## 8. Backfill the review link

An entry created before review links existed may lack one:

```bash
CRUCIBLE=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crucible_path.py) || exit 1
ENTITY=challenge   # or bug
LABEL=<label>
PR_URL=$(gh pr view --json url --jq .url)
EXISTING=$("$CRUCIBLE" --json "${ENTITY}" show --label="${LABEL}" | jq -r '.review_link // ""')
if [ -z "${EXISTING}" ]; then
  "$CRUCIBLE" "${ENTITY}" update --label="${LABEL}" --replace-review-link="${PR_URL}"
fi
```

## 9. Report

- Comments addressed and resolved (thread IDs or file:line).
- Drafted replies awaiting the user, with the text inline.
- Confirmation that every comment is fixed and resolved, or drafted and open.
- The pushed commit and the build result (or that CI was left to build).
- Whether the review link was backfilled, and any Crucible follow-ups filed.

This skill does not post replies, approve or merge the PR, or run `/phoe:verify`.
