---
name: bugfix
description: Fixes one Crucible bug end-to-end, by label or "next" (highest severity), through reproduction, diagnosis, verify, review and a PR, stopping at review status. Use when the user asks to fix or pick up a bug.
---

Fix one Crucible bug with the user supervising. `<kind>` in the shared steps is `bug`.

Load each reference at the step that needs it:

- [Challenge workflow](../../references/challenge-workflow.md): bootstrap, claim and worktree,
  acceptance criteria, publish, landing, feedback log.
- [Dispatch briefs](../../references/dispatch-briefs.md): reviewer dispatch and prompts, acting on
  findings, the review gate.

At most **3** subagents run at once.

## Arguments

- **`<label>`**: the bug to fix.
- **`next`**: the highest-severity `todo` bug.

## 1. Bootstrap

Follow [challenge workflow](../../references/challenge-workflow.md) §1.

## 2. Resolve the bug

**For `next`:** detect landed bugs in `review` ([challenge
workflow](../../references/challenge-workflow.md) §2), then pick from
`"$CRUCIBLE" --json bug list --status=todo` by severity (crash > major > moderate > minor), then
priority (critical > high > medium > low), then lowest ID. If none is eligible, tell the user and
stop.

**For a label:** `"$CRUCIBLE" bug show --label=<LABEL>`.

**Resuming.** If `.claude/handoffs/bug-<LABEL>-checkpoint.md` exists, say "Resuming from
checkpoint" with its summary. The bug is already `active` and its worktree exists, so enter that
worktree instead of claiming and creating one in Step 3; skip Steps 4 and 5 and start Step 6 from
its Remaining Work. Delete the checkpoint once the fix passes verification.

## 3. Claim, context and worktree

Claim the bug and create and enter its worktree, based on `origin/main`, per
[challenge workflow](../../references/challenge-workflow.md) §3; run everything after this from the
worktree. Show the title, description, severity, reproduction steps, acceptance criteria and
verification steps.

## 4. Reproduce

Follow the reproduction steps exactly, confirm the bug manifests, and record what happens: errors,
stack traces, log output. If it cannot be reproduced, tell the user, move the bug back to `todo`
and stop; never ship a speculative fix.

## 5. Diagnose

Use the `superpowers:systematic-debugging` skill. Trace from the reproduction evidence to the root
cause, and state what code is wrong and why it produces the observed behavior.

**Context checkpoint.** If diagnosis is consuming significant context, write the checkpoint below,
tell the user "I've written a checkpoint; start a new session and run `/phoe:bugfix <LABEL>` to
continue", and stop.

```markdown
# Checkpoint: bug-<LABEL>
## Bug
<title and one-line description>
## Reproduction
<what was observed>
## Root Cause
<root cause with file:line references>
## Proposed Fix
<approach>
## Remaining Work
<concrete steps>
```

## 6. Fix

Implement the fix. Before writing C++, read `Docs/StyleGuide.md` and
`${CLAUDE_PLUGIN_ROOT}/references/tooling.md`. Comments default to none: one line, two or three for
the genuinely complex, why rather than what (`Docs/StyleGuide.md` §Comments). A TODO is one line
describing the work, with no path, line number, label, PR number, branch or date, and never
narrates the change you just made (§TODO Comments).

**Regression trial.** Guard against the class of flaw recurring, not every bug mechanically. Add a
trial when the root cause is a pattern that exists elsewhere (a missed lifetime check, an unhandled
enum case, a race on a shared field; consider the sibling sites too), the fix is subtle enough for
a refactor to undo silently, the bug breaks an invariant nothing else enforces, or the repro is
cheap to mechanize. Skip it for an obviously correct, self-contained fix (typo, one-off null check,
wrong literal), glue code due to be rewritten, or a repro that needs specific hardware, manual
interaction or one platform. Write it by dispatching the `invoke-test-engineer` prompt as a
general-purpose agent with the absolute worktree path, the fix diff, the root cause and the
reproduction steps, so the trial exercises the flaw itself
([dispatch briefs](../../references/dispatch-briefs.md) §1).

## 7. Verify

First confirm new names ([challenge workflow](../../references/challenge-workflow.md) §9).

1. Re-run the reproduction steps: the bug no longer manifests.
2. Run the bug's verification commands.
3. Run `/phoe:verify` for the profiles its §2a requires, and name them in the report; a run that
   aborts at the toolchain audit has tested nothing (§2b).

Fix and re-run until everything passes.

## 8. Acceptance criteria

Follow [challenge workflow](../../references/challenge-workflow.md) §4.

## 9. Review

1. Commit the fix on the branch (`git add -A`, then a message referencing the label) and freeze the
   range ([dispatch briefs](../../references/dispatch-briefs.md) §2).
2. Dispatch the quality reviewer (with the bug sentence), and once it passes, the adversarial
   reviewer on the same SHA, per dispatch briefs §1-§4: `Explore`, read-only, with the verbatim
   `## Bug Contract` from `"$CRUCIBLE" bug show --label=<LABEL>` and the preamble. No PR opens
   without the adversarial pass.
3. Gate on dispatch briefs §7. For each CRITICAL or WARNING, act per §6, commit, re-run
   `/phoe:verify` and Step 8, re-freeze, and re-run both reviewers. A WARNING you judge a false
   positive or out of scope goes to the user, with your reasoning, to waive; record each waiver in the
   report. If the trend stalls, stop and show the user the round-by-round findings.

Squashing review fixups is optional; leave nothing uncommitted.

## 10. Move to review

```bash
"$CRUCIBLE" bug move --label=<LABEL> review
```

The fix is not done until this succeeds. If it fails, stop and surface the error; do not report the
bug fixed.

## 11. Feedback log

Follow [challenge workflow](../../references/challenge-workflow.md) §8 with
`--run "/phoe:bugfix <label>"`. Do not mention the log in the report.

## 12. Publish

Follow [challenge workflow](../../references/challenge-workflow.md) §5. The summary covers the bug,
its root cause and the fix; the trailer is `Crucible: #<id> <label>`, with no `Saga:` line.

## 13. Report

Tell the user what was fixed and its root cause, the verification results (profiles named, and that
the reproduction no longer triggers), the branch `bug/<branch-label>`, **PR #<N>** and its URL (or
"branch left local; not pushed"), any waived WARNING, and that the bug is in `review` for the user
to inspect.

Do not merge the PR. The bug moves to `merged` only once landing is proven; then run
[challenge workflow](../../references/challenge-workflow.md) §7 steps 1 and 4 (move it to `merged`,
clean up).
