---
name: implement
description: Implements one Crucible challenge end-to-end under user supervision, by label or "next", through verify, review and a PR, stopping at review status. Use when the user asks to implement or pick up a challenge.
---

Implement one Crucible challenge with the user supervising. To run several autonomously, use
`/phoe:execute`.

Load each reference at the step that needs it:

- [Challenge workflow](../../references/challenge-workflow.md): bootstrap, claim and worktree,
  acceptance criteria, publish, sibling reconciliation, landing, feedback log.
- [Dispatch briefs](../../references/dispatch-briefs.md): reviewer dispatch and prompts, acting on
  findings, the review gate.
- [Parallel integration](../../references/parallel-integration.md): dependent PRs and semantic
  sibling overlap. Its recorded-parent and replacement-branch gates supersede ordinary rebase
  guidance.
- [Targeted compilation](../../references/targeted-compilation.md): early diagnostics for one TU.

At most **3** subagents run at once (test writer, reviewers, fix passes; a background agent counts
until its notification arrives). A fourth waits for one to return.

## Arguments

- **`<label>`**: the challenge to implement.
- **`next`**: the highest-priority eligible `todo` challenge.
- *(none)*: if there are no todo challenges, ask the user to run `/phoe:plan` first.

## 1. Bootstrap

Follow [challenge workflow](../../references/challenge-workflow.md) §1.

## 2. Resolve the challenge

**For `next`:**

1. Detect landed challenges in `review` ([challenge workflow](../../references/challenge-workflow.md)
   §2).
2. List sagas and todo challenges: `"$CRUCIBLE" --json saga list` and
   `"$CRUCIBLE" --json challenge list --status=todo`. For each `--status=blocked` challenge whose
   blocker is now `merged`, `"$CRUCIBLE" challenge unblock <ID> todo` and add it to the pool.
3. A saga challenge is eligible only when every earlier challenge in its saga is `merged` or
   `canceled`; orphans always are. One whose predecessor is still `active` or in `review` waits; do
   not block it, since saga order already encodes that dependency.
4. Pick the highest priority (critical > high > medium > low), then the lowest ID. If nothing is
   eligible, tell the user and stop.

**For a label:** `"$CRUCIBLE" challenge show --label=<LABEL>`.

**Resuming.** If `.claude/handoffs/<LABEL>-checkpoint.md` exists, say "Resuming from checkpoint"
with its summary. The challenge is already `active` and its worktree exists, so enter that worktree
instead of claiming and creating one in Step 3; skip Step 4's exploration and start Step 5 from its
Remaining Work. Delete the checkpoint once the implementation passes verification.

## 3. Claim, context and worktree

1. Claim the challenge and create and enter its worktree, based on `origin/main`, per
   [challenge workflow](../../references/challenge-workflow.md) §3. Run everything after this from
   the worktree.
2. Show the title, description, acceptance criteria and verification steps.
3. Read the comments: `"$CRUCIBLE" challenge comments --label=<LABEL>`. They are newer than the
   description and win where the two disagree; name the stale description text and what you
   followed instead.
4. If the challenge is in a saga, `"$CRUCIBLE" saga show --label=<SAGA_LABEL>` and show its position
   and the saga's progress.

## 4. Explore

Read the affected files, references and tags, and explore what has to change. In a saga, read the
completed siblings for patterns.

**Context checkpoint.** On a large challenge (several modules, many files, long exploration), write
a checkpoint at a natural break (after exploration, or halfway through with much left), tell the
user "I've written a checkpoint to `.claude/handoffs/<LABEL>-checkpoint.md`; start a new session
and run `/phoe:implement <LABEL>` to continue with fresh context", and stop.

```markdown
# Checkpoint: <LABEL>
## Challenge
<title and one-line description>
## Understanding
<what code does what, dependencies, patterns found>
## Decisions
<design choices and why>
## Implemented So Far
<files changed and what was done; empty before implementation>
## Remaining Work
<concrete steps still needed>
## Open Questions
<anything needing user input>
```

## 5. Plan and implement

Enter plan mode, plan (starting from the `strategy` field when there is one), then implement.
When Ryan rules on a design change along the way, run the decision-time pass
([challenge workflow](../../references/challenge-workflow.md) §6a) before writing more code.
Before writing C++, read `Docs/StyleGuide.md` and `${CLAUDE_PLUGIN_ROOT}/references/tooling.md`.
Comments default to none: one line, two or three for the genuinely complex, why rather than what
(`Docs/StyleGuide.md` §Comments). A TODO is one line describing the work, with no path, line
number, label, PR number, branch or date, and never narrates the change you just made
(§TODO Comments).

**Trials** are required for new public interfaces, non-trivial logic (algorithms, state machines,
parsing, validation, calculations) and changed observable behavior. They are not required for
build-system, profile or config-only changes, pure wiring to already-tested code, or platform code
only that platform's CI can exercise. Write them by dispatching the `invoke-test-engineer` prompt
as a general-purpose agent with the absolute worktree path, the diff and the module context
([dispatch briefs](../../references/dispatch-briefs.md) §1), and ask it to end with a
`## Workflow Friction` section or `none`.

## 6. Verify

First confirm new names ([challenge workflow](../../references/challenge-workflow.md) §9).

1. Run the challenge's verification commands.
2. Run `/phoe:verify` for the profiles its §2a requires.

Fix and re-run until everything passes.

## 7. Acceptance criteria

Follow [challenge workflow](../../references/challenge-workflow.md) §4. Do not start review until
every mechanically verifiable criterion is met.

## 8. Review

1. Commit the work on the branch (`git add -A`, then a message referencing the label) and freeze the
   range ([dispatch briefs](../../references/dispatch-briefs.md) §2).
2. Dispatch the quality reviewer, and once it passes, the adversarial reviewer on the same SHA, per
   dispatch briefs §1-§4: `Explore`, read-only, with the verbatim contract and the preamble. No PR
   opens without the adversarial pass.
3. Gate on dispatch briefs §7. For each CRITICAL or WARNING, act per §6, commit, re-run
   `/phoe:verify` and Step 7, re-freeze, and re-run both reviewers. A WARNING you judge a false
   positive or out of scope goes to the user, with your reasoning, to waive; never drop one silently,
   and record each waiver in the report. If the trend stalls, stop and show the user the
   round-by-round findings.
4. Leave SUGGESTION and NOTE findings out of the report unless one is particularly insightful.

Squashing review fixups into one commit is optional; leave nothing uncommitted.

## 9. Move to review

```bash
"$CRUCIBLE" challenge move --label=<LABEL> review
```

The work is not done until this succeeds. If it fails, stop and surface the error; do not report
the challenge done.

## 10. Feedback log

Follow [challenge workflow](../../references/challenge-workflow.md) §8 with
`--run "/phoe:implement <label>"`, collecting the test writer's, reviewers' and fix passes' friction
plus your own as Implementer. Do not mention the log in the report.

## 11. Reconcile siblings and docs

Run the pre-merge pass of [challenge workflow](../../references/challenge-workflow.md) §6. A real
scope problem in a later challenge goes in the report for the user to decide on re-planning.

## 12. Publish

Follow [challenge workflow](../../references/challenge-workflow.md) §5, writing the summary from the
title and the key changes; Crucible holds the detail. A dependent PR follows
[parallel integration](../../references/parallel-integration.md): confirm native stack identity, or
recover the child-only work onto main, before presenting it as ready.

## 13. Report

Show saga progress (`"$CRUCIBLE" saga show --label=<SAGA_LABEL>`) when in a saga, and tell the user:

- what was implemented;
- trials added (by name), or why none were needed;
- verification results, naming the profiles;
- the branch, `challenge/<branch-label>`;
- sibling and doc reconciliation (the required line from §6), and any waived WARNING or re-cut
  candidate;
- **PR #<N>** and its URL, or "branch left local; not pushed";
- that the challenge is in `review` for the user to inspect.

Do not merge the PR. The challenge moves to `merged` only once landing is proven
([challenge workflow](../../references/challenge-workflow.md) §2).

**On landing**, here or in a later run's Step 2: run challenge workflow §7, then report the next
ready challenge from Step 2's selection (label, title, priority, `/phoe:implement <label>`), or say
the saga is done or nothing is unblocked. Do not start it. `/phoe:plan` creates challenges or
extends a saga.
