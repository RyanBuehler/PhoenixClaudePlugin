---
name: pr-fixup
description: Use when addressing review feedback on an open PR — pulls main, resolves any merge conflicts, triages and addresses review comments, reconciles resolved threads, then verifies via local build before pushing. Auto-activates on phrases like "address PR feedback", "fix the review comments", "handle PR review", "respond to reviewers".
---

# PR Fixup — Address Review Feedback

A linear workflow for the common case: a PR has new review comments, possibly drifted from main, and needs another revision pushed.

## Workflow

### 1. Sync with main

From the PR branch:

```bash
git fetch origin main
git merge origin/main          # or rebase, if the branch's convention is rebase
```

If conflicts arise, resolve them before doing anything else. Investigate each conflict — never blindly take one side. If a conflict touches code a review comment also references, resolve the conflict first so subsequent comment fixes apply to the merged state.

If no conflicts, continue.

### 2. Pull review comments

```bash
gh pr view --comments
gh api repos/{owner}/{repo}/pulls/{number}/comments    # inline review comments
gh api repos/{owner}/{repo}/pulls/{number}/reviews     # review summaries
```

Collect every unresolved comment. Include both top-level PR comments and inline code comments. Note thread IDs so you can resolve them later.

### 3. Triage

Group comments into:

- **Actionable** — clear code change requested.
- **Question** — needs an answer, not a code change.
- **Disagreement** — the reviewer's request conflicts with intent or another constraint; surface to the user before acting.
- **Out of scope** — file a Crucible follow-up rather than expanding the PR.

**No comment falls through the cracks.** Every comment must end in one of two terminal states:
1. **Fix landed + thread resolved** (Actionable that was addressed).
2. **Reply drafted, thread left unresolved** (Question, Disagreement, Out-of-scope, or Actionable-but-deferred).

A resolved thread without a fix, or an unaddressed comment without a drafted reply, is a bug in this workflow.

For each actionable comment, **verify the cited code claim** per the plugin CLAUDE.md "Verify review-comment code claims before acting" rule — line numbers drift across PR updates. If the cited construct isn't on the referenced line or nearby, stop and ask the reviewer instead of guessing.

### 4. Address actionable items

Make the requested changes, one comment at a time. Keep edits scoped — a fixup commit isn't a refactor opportunity.

For every non-actionable comment (Question, Disagreement, Out-of-scope, or Actionable-but-deferred), **draft a reply** explaining the answer, the disagreement rationale, or the Crucible follow-up label. Drafts stay local; the user posts. A non-actionable comment with no drafted reply is incomplete work.

### 5. Reconcile threads

Once a comment's fix is in, resolve the thread on GitHub:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { isResolved }
    }
  }' -f threadId="<thread-id>"
```

Look up `threadId` values via the GraphQL `pullRequest.reviewThreads` query.

**Resolution invariants:**
- Resolve a thread only if a commit in this fixup actually addresses the ask. Verify the diff before resolving — never resolve speculatively.
- Never resolve Question, Disagreement, or Out-of-scope threads. Those carry drafted replies and stay open for the user.
- Before finishing this step, audit: every Actionable thread → resolved with a fix; every other thread → unresolved with a drafted reply.

### 6. Build to verify

Run `/phoe:build` for the relevant application profile. Do **not** run `/phoe:verify` here — that gate is for the user. The goal is a sanity check: does the code at least compile after the merge plus the fixes?

### 7. Push

If the build passes, push immediately:

```bash
git push
```

Pushing the PR branch fires GitHub's `pull_request.synchronize` webhook, which is what re-triggers CI. Push as soon as the local build is green so that webhook fires early and CI runs in parallel with the user's review. Don't batch with other unrelated work — every extra commit before the push delays `synchronize` by that much.

If the build fails, fix the failure, rebuild, and push once it's green. Repeat until clean. **Never push a known-broken build** — pushing failures wastes a CI cycle and signals false progress.

### 8. Report

Tell the user:
- Which comments were addressed and resolved (thread IDs / file:line).
- Which have drafted replies awaiting the user (questions, disagreements, deferred, out-of-scope) — include the draft text inline.
- Confirmation that every comment is in one terminal state — fixed+resolved or drafted+unresolved.
- Build status and the pushed commit.
- Any out-of-scope items filed as Crucible follow-ups.

## What this skill does NOT do

- **Post comment replies.** Drafted replies stay drafted; the user posts.
- **Approve or merge the PR.** Out of scope.
- **Run `/phoe:verify`.** That's the user's commit gate, not a fixup gate.
- **Force-push or rewrite published history.** Use plain `git push`. If a rebase is required, surface that to the user first.
- **Resolve threads the user marked unresolved.** If a thread was reopened, leave it alone unless explicitly told to re-resolve.
