---
name: execute
description: Autonomously execute N Crucible challenges via subagents (at most 3 at once) with zero user interaction. Runs independent challenges in parallel, dependent ones as stacked PRs, and groups related small challenges into one PR.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep, Agent
---

Execute Crucible challenges autonomously through subagents and report at the end. The challenge
JSON is the whole spec; nothing waits on the user.

Load each reference at the step that needs it:

- [Challenge workflow](../../references/challenge-workflow.md): bootstrap, claim and worktree,
  publish, sibling reconciliation, landing, feedback log.
- [Dispatch briefs](../../references/dispatch-briefs.md): reviewer dispatch and prompts, fix
  passes, the review gate, waiting on builds.
- [Implementer brief](../../references/implementer-brief.md): the implementer prompt.
- [Parallel integration](../../references/parallel-integration.md): sibling contracts before
  dispatch and after rebases, and the stack lifecycle.
- [Negative controls](../../references/negative-controls.md): witness rows for test-writing briefs
  and the verification report.

## Arguments

- **`<N>`**: the next N eligible challenges (saga-aware selection).
- **`<saga-label>`**: every remaining todo challenge in that saga.
- **`next`**: the next one eligible challenge.

## Stacks and verification points

Terms, used only in these senses: a **stack** is a chain of dependent work; a **layer** is one link
of it; a **group** is several challenges combined onto one branch and PR (Step 3), which counts as
one layer; **wave** N is every stack's Nth layer; **verification point** and **checkpoint** are
defined below.

**Dependent work is a stack.** A challenge that depends on unmerged work in this run (a saga
successor, or the later of two challenges with overlapping `affected_files`) is a **layer**: its own
branch and worktree off the parent layer's tip, and its own PR based on the parent's branch. A layer
starts once its parent has committed, not after the parent's review or verify. Independent stacks
(a lone challenge is a stack of one) run in parallel. Stack lifecycle follows [parallel
integration](../../references/parallel-integration.md) §Native stack lifecycle; Ryan merges
bottom-up with "Create a merge commit", never "Update branch".

**Verify once per stack, at its top.** Builds are the bottleneck: each worktree's first build is
cold, and all builds share a box that is also a CI runner.

- The **verification point** is the top layer, verified after review fixes and main integration
  (4d), so one `/phoe:verify` covers every layer. Its implementer only builds; lower layers do not
  bootstrap or build, and their build-dependent Verification Commands run at the verification point.
- Add a **checkpoint** (verify a lower layer in its own worktree) only when the layer edits a build
  profile, Forge, the toolchain or CI; changes a module interface the layers above build against;
  reports correctness concerns; or sits about five layers above the last checkpoint.
- Fix and triage passes run an incremental `forge build` where the layer already builds, nothing
  where it defers. Verify after the last review round, not every round, and never re-verify a tree
  nothing changed.
- No PR opens without a green verify at or above its layer. Each PR's CI proves its layer builds
  alone.

**Carrying a lower-layer fix up.** Bottom-to-top, from each child's worktree. Unpushed: `git -C
<child-worktree> rebase --onto challenge/<parent-branch-label> <old-parent-tip>`. Pushed: never
rebase; `git -C <child-worktree> merge challenge/<parent-branch-label>`, then push.

## Concurrency cap

At most **3** subagents run at once across the whole run: implementers, fix and triage passes and
reviewers all count, and a background agent counts until its notification arrives. A wave with more
than 3 layers runs in batches, dispatching the next as one returns. One layer's three reviewers fill
the cap on their own. Unbounded fan-out has exhausted Ryan's usage in a single run; grouping
(Step 3) is the other lever.

## 1. Bootstrap

Follow [challenge workflow](../../references/challenge-workflow.md) §1. Then check the main
checkout is clean (`git status --porcelain`); if not, stop and tell the user to commit or stash.

## 2. Resolve challenges

**For `<N>` or `next`:** the pool is every `todo` challenge, in a saga or an **orphan** (in none);
both compete equally.

1. Detect landed challenges in `review` ([challenge workflow](../../references/challenge-workflow.md)
   §2).
2. List the pool: `"$CRUCIBLE" --json saga list`, `"$CRUCIBLE" --json challenge list --status=todo`,
   and the orphans with `... --status=todo --no-saga`.
3. Unblock: for each `"$CRUCIBLE" --json challenge list --status=blocked` entry whose `blocked_by`
   challenge is now merged, `"$CRUCIBLE" challenge unblock <ID> todo`.
4. Saga order: keep only challenges whose saga predecessors are all `merged` or `canceled`. Orphans
   pass.
5. Implicit cross-saga blockers, precision first. Prose can tie a challenge to unmerged work in
   another saga. A false skip strands an eligible challenge while a missed blocker costs one later
   verify failure, so skip only when all three hold against the same unmerged challenge (orphans
   included, both ways):
   - **A.** The candidate's description, strategy or criteria contain a qualified token:
     `Namespace::Identifier`, `Module.Type` or a file path. Bare PascalCase names do not count.
   - **B.** The unmerged challenge has the token in its prose and its `affected_files`, so it
     introduces or modifies it rather than mentioning it.
   - **C.** The two challenges' `affected_files` overlap.

   Record the skip as `blocked by <other-label> (saga #<id> or orphan) via <Token> in <file>`. It is
   a scheduling hint, not a Crucible block: the user may judge the dependency stale.
6. Pick by priority (critical > high > medium > low), then lowest ID, until N are selected. Skip a
   candidate another candidate blocks.
7. Screen out owner-gated challenges before any setup: a description or strategy whose first
   sentence opens with a gate ("DESIGN FORK FOR RYAN", "Do not implement as written", "Ryan picks
   before implementation") is not autonomously executable.
8. Audit each selected challenge against `origin/main`. Unrelated PRs do deliver challenges; where
   the work is done, say so and move the challenge rather than producing an empty diff.

**For `<saga-label>`:** `"$CRUCIBLE" --json saga show --label=<SAGA_LABEL>`. Its todo challenges,
in saga order, form one stack. Orphans are not included.

Report every skip (owner-gated, already delivered, implicit blocker, wave full) in the final
report. If nothing is eligible, report that and stop.

## 3. Plan stacks and groups

Build the dependency graph:

- **Same-saga edge:** the lower saga position goes first.
- **File-overlap edge:** of two challenges with overlapping `affected_files`, the lower ID goes
  first.

The edges form stacks. A layer has one parent, so a challenge with predecessors in two stacks joins
them into one, ordered by ID. Mark each stack's verification point and checkpoints.

**Then group where it makes sense.** Challenges that ship better as one PR share one branch, one
implementer, one verify, one review round and one PR. Group when they share a surface (a module or
overlapping `affected_files`; a file-overlap edge between two small challenges is usually better
grouped than stacked) or are each a few lines or prose. Never group a large or risky challenge,
challenges in unrelated modules, or more than 4. When unsure, don't: a failed member blocks its
whole group.

Print the plan:

```
Execution Plan:
  Stack A: #42 add-viewport-resize -> #43 wire-canvas-events -> #44 canvas-resize-trials [verify]
  Stack B: #54 forge-compiler-launcher [checkpoint: edits Forge] -> #55 forge-launcher-docs [verify]
  Stack C (group, one PR): #57 rename-tessera-padding + #58 tessera-padding-docs [verify]
  Wave 0 (parallel): #42, #54, #57+#58    Wave 1: #43, #55    Wave 2: #44
```

## 4. Execute waves

4a-4c and 4e-4g run per layer; 4d and 4h run per verification point or checkpoint, covering every
reviewed layer beneath it.

### Docs-only fast path

A challenge is **docs-only** when its `affected_files` and criteria touch no C++, build or test
code (a design doc, spec or other prose). Everything else runs 4a-4h unchanged. For docs-only:

- **No build and no `/phoe:verify`.** Skip the Forge bootstrap; drop Your Job steps 1 and 6 from
  the implementer brief, say the change is prose-only, and tell it to ignore "task tools haven't
  been used recently" reminders (the orchestrator tracks the wave).
- **4d becomes a grounding check.** Scan the draft for path references that do not resolve
  (`Engine/<X>/`, `Project/<X>/`, nonexistent helpers, toolchains or inspector pages) and
  determinism claims with no stated posture, and fix them before review.
- **One review round.** Run the adversarial reviewer (spec and quality are optional adds) and one
  fix pass, which must clear every CRITICAL and WARNING; then advance to the PR, logging suggestions
  and notes. Run a second round only if the first found 3 or more CRITICALs. A CRITICAL in a doc
  means a wrong number or assumed infrastructure, which the PR's review can weigh.

### 4a. Setup

Each layer gets a branch by one strategy, fixed for the wave:

- **Branch-per-challenge:** independent; its own branch and worktree off main, its own PR.
- **Stack layer:** dependent; its own branch and worktree off the parent layer's tip, its own PR
  based on the parent's branch. Never extend the parent's branch instead.
- **Combined branch:** one Step 3 group; one branch and worktree named after its lowest-ID member,
  one PR. Never rename it (the hook requires the folder to match the branch). It sits in its latest
  member's wave and can be a stack layer.

For each challenge, run [challenge workflow](../../references/challenge-workflow.md) §3 from the
main repo root, with these differences:

- A challenge no longer `todo` was claimed by a parallel run: drop it and log "Pre-empted by
  parallel agent". A claim to undo (pre-empted, blocked, base-ref conflict) moves back to `todo`.
- `<base-ref>` is `origin/main` for an independent challenge or a stack's bottom, and
  `challenge/<parent-branch-label>` for a layer above it. Record that tip as the layer's **parent
  SHA**: its review base, restack point and PR range start.
- A group member after the first reuses the group's worktree; claim it as normal.
- Skip §3 step 4 (entering); 4b places implementers.
- Bootstrap Forge (§3 step 5) only in a worktree that will build: a verification point or
  checkpoint. A deferred layer or docs-only challenge never builds. Each building worktree pays a
  cold first build of a few minutes.

### 4b. Implement

Dispatch one implementer per layer into its worktree, with the
[implementer brief](../../references/implementer-brief.md). Its Verification Role is BUILD at a
verification point or checkpoint and DEFER elsewhere.

**Placing an implementer.** The Agent tool has no `cwd`: a subagent inherits the orchestrator's. In
a background session a subagent gets native `Write`/`Edit` and `git` only in the one worktree the
orchestrator has entered with `EnterWorktree(path=<absolute path>)`; entering another revokes the
previous one.

- **Serial (default):** enter A, dispatch A, await it, enter B, and so on. A stack's layers are
  serial anyway; parallelism comes from independent stacks.
- **Parallel:** dispatch up to 3 at once and tell each to author files through Bash (single-quoted
  heredocs for new files, a `python` exact-string replace with `assert count == 1` for edits).
  Their `git` is refused, so the orchestrator enters each worktree in turn to commit for it.
- Use the general-purpose agent. Never pass `isolation: "worktree"`: it creates a fresh worktree
  off main and ignores the prepared branch. The `phoe:invoke-*` specialists carry it, so they are not
  implementers. Never let a subagent call `EnterWorktree`; it reports success and then breaks Bash.
- Forge bounds build load itself (`/phoe:verify` §2b); only cold bootstraps need serializing.

### 4c. Handle implementer results

| Status | Action |
|--------|--------|
| **DONE** | Dispatch the next layer, then review it (4e). 4d waits for the verification point. |
| **DONE_WITH_CONCERNS** | Correctness or scope concerns: dispatch a targeted fix subagent, and consider a checkpoint. Observations: note them and proceed. |
| **BLOCKED** | Retry once with the affected files, the files it named and more codebase context in the brief. Blocked again: block the challenge in Crucible with a detailed reason, write a checkpoint, keep the branch and commits, and move on. |
| **NEEDS_CONTEXT** | Retry once, answering its questions from the codebase, the core rules and sibling challenges. Again: block it with the unanswered questions as the reason, keep the branch, and move on. |

A block needs a blocker (`challenge move ... blocked` is refused):

```bash
"$CRUCIBLE" challenge block <ID> --blocked_by=<BLOCKER_ID>
```

Layers above a blocked layer name that layer as the blocker. The failing challenge itself needs a
blocker challenge, filed first with `/phoe:crucible`, that describes the failure.

Write the checkpoint to `.claude/handoffs/<LABEL>-checkpoint.md`:

```markdown
# Checkpoint: <LABEL>
## Challenge
<title and description>
## What Was Attempted
<summary of the subagent's work>
## Why It Failed
<the specific failure from its report>
## Suggested Next Steps
<concrete steps for a human to continue>
## Subagent Report
<the full report>
```

Never revert a blocked challenge's branch or discard its commits: partial work is context for
resuming with `/phoe:implement <label>`. Keep branches, commits and checkpoint files.

### 4d. Integrate and verify

Runs per verification point or checkpoint once 4f converges, in the layers' own worktrees. Local
`main` is never checked out, merged into or committed to: parallel agents share it, and a PR built
from it carries their commits. First confirm the stack's new names ([challenge
workflow](../../references/challenge-workflow.md) §9) in one question round; other stacks keep
working meanwhile. Then integrate main, so one verify covers the renames and the integration:

1. Rebase the stack's bottom onto `origin/main`, then restack each layer above it (`rebase --onto`,
   as in carrying a fix up). Skip when main has not moved since the bottom was created. Check
   sibling contracts after the rebase ([parallel
   integration](../../references/parallel-integration.md) §Independent siblings and semantic
   overlap).
   ```bash
   git -C .claude/worktrees/challenge-<bottom-branch-label> fetch origin main
   git -C .claude/worktrees/challenge-<bottom-branch-label> rebase origin/main
   ```
2. On conflict, `rebase --abort` and block that layer and every layer above it with "Rebase conflict
   with origin/main on files: <list>". Keep the branches.
3. Run `/phoe:verify` in the verification point's worktree for the profiles `/phoe:verify` §2a
   requires across every covered layer (one run covers one profile; never CI's lane set). Record
   the profiles verified.
4. Run every covered layer's Verification Commands.
5. On failure, attribute it: the layer whose own range (`git diff --name-only <parent-sha>
   <layer-tip>`) touched the failing file; when none or several match, verify the midpoint layer. A
   fix subagent commits there; restack the layers above and verify again. On a second failure, block
   that layer and those above it with the error output, keeping the branches; the layers below can
   still ship once the highest of them verifies.

### 4e. Review

The adversarial reviewer is a mandatory gate: a layer without it never reaches 4h, because nothing
else stands between an autonomous diff and `origin`. Review layers in ID order. For each, dispatch
the spec, quality and adversarial reviewers at once and wait for all three before the next layer. A
group is reviewed once, over the whole branch, with every member's contract in each brief.

Assemble and dispatch per [dispatch briefs](../../references/dispatch-briefs.md) §1-§4: `Explore`
with the read-only clause, a frozen range (a stack layer's base is its parent SHA), the verbatim
contract, a build state saying `/phoe:verify` runs after review, the preamble, and the §4 prompts.

### 4f. Handle review results

Fix and triage subagents commit in the layer's own worktree. Passes for the same layer run one at a
time, each finishing (committed, and built where the layer builds) before the next starts. Carry a
fix up before the layers above it are next reviewed. If a fix would change the shape of the work
rather than touch it up, block the challenge and let the user re-plan.

For each layer, in ID order:

- **Blocking** (spec FAIL, or a quality or adversarial CRITICAL or WARNING): dispatch a fix
  subagent with every reviewer's blocking findings and the verbatim instruction from
  [dispatch briefs](../../references/dispatch-briefs.md) §6, split into narrow passes when the set
  is large. Then re-run all three reviewers and judge convergence by dispatch briefs §7. When the
  trend stalls, regresses or hits the backstop, block the challenge with the full feedback and the
  round-by-round trend, keep its branches, and move on. With no human to waive one, an unresolved
  WARNING blocks.
- **SUGGESTION** (quality or adversarial, merged and deduplicated): dispatch a triage subagent. It
  implements each suggestion that is in scope, correct and valuable, and defers the rest as a
  one-line `// TODO:` at the relevant code (`Docs/StyleGuide.md` §TODO Comments). Nothing is dropped
  silently. It commits to the branch; do not re-review. Log implemented and deferred counts by
  source.
- **NOTE:** log it.

Surface every `## Also Noticed` in the final report. When review cannot run, the gate is unmet
(dispatch briefs §7): the layer stops short of `review`, and the report and PR body say so.

### 4g. Move to review

1. `"$CRUCIBLE" challenge move --label=<LABEL> review`
2. Run the pre-merge pass of [challenge workflow](../../references/challenge-workflow.md) §6.

### 4h. Publish

**Race check.** A parallel agent may have landed equivalent work, and a rebase would then drop your
commits as cherry-pick-equivalent, leaving an empty PR:

```bash
git fetch origin main
git log origin/main --oneline -i --grep="<label>" -10
```

If a match delivers this challenge, mark it merged, remove its worktree (branch-per-challenge only)
and `git branch -D challenge/<branch-label>`, log "Pre-empted by parallel agent", and move on.

Otherwise push the verified tree even if main has moved since 4d: each PR's CI builds its merge with
main. Repeat 4d first only when the new main commits touch the stack's files, modules or shared
contracts ([parallel integration](../../references/parallel-integration.md) §Independent siblings
and semantic overlap); a clean rebase there can still collide at runtime. Regenerate a tree-wide
sweep on the new base rather than rebasing it, since a rebase misses instances main added. Check
every tracker record you filed against the freshly fetched `origin/main`; a long run's worktree
drifts far behind.

Publish per [challenge workflow](../../references/challenge-workflow.md) §5, exiting each worktree
before starting the next:

- **Branch-per-challenge:** one PR; remove the worktree after pushing.
- **Stack layer:** push bottom-to-top. Each PR above the bottom uses `--base
  challenge/<parent-branch-label> --draft` and adds `Stacked on PR #<parent>; layer range
  <parent-sha>..<tip>` to its body. Once its parent lands, the session that sees it retargets the PR
  to main (`gh pr edit <N> --base main`) and marks it ready. Keep every layer's worktree until the
  whole stack is pushed; a late fix may still have to be carried up.
- **Combined branch:** once every member has reached `review`, push once and open one PR listing
  them all, with the review link recorded on each; then remove the shared worktree.

Later fixes (review comments, conflicts, CI failures) use `/phoe:pr-fixup`.

## 5. Feedback log

Follow [challenge workflow](../../references/challenge-workflow.md) §8 with
`--run "/phoe:execute <args>"`, collecting the friction sections of every implementer, reviewer and
fix pass, plus your own as orchestrator (dispatch, lock contention, rebase, Crucible, publish).

## 6. Report

Open with the names Ryan confirmed or renamed in 4d.

```
/phoe:execute Results
=====================

Names confirmed:
  RasterBaselinePass (wire-raster-baseline) -- the pass that records the reference image; was ReferenceRasterPass

| Challenge | Wave | Status | Branch | PR | Notes |
|-----------|------|--------|--------|----|-------|
| add-viewport-resize | 0 | review | challenge/add-viewport-resize | #1234 | -- |
| forge-compiler | 0 | blocked | challenge/forge-compiler | -- | Build failure: missing include |
| wire-canvas-events | 1 | review | challenge/wire-canvas-events | #1235 | Fixed 1 WARNING (large function) before review |

Saga Progress:
  synthetic-input: 3/6 complete (was 2/6)
  (orphan): 1 challenge processed this run

Blocked Challenges:
  forge-compiler: Build failure in ForgeCompiler.cpp:42 -- missing include for <filesystem>.
  Checkpoint written to .claude/handoffs/forge-compiler-checkpoint.md
  Resume with: /phoe:implement forge-compiler

Stats: 2 completed, 1 blocked, 0 skipped
Feedback logged to: .claude/AGENT_FEEDBACK.md
```

Also include:

- Each stack bottom-to-top: each PR as **PR #<N>** with URL, its base, its strategy and where it
  was verified (profiles), plus "merge bottom-up with 'Create a merge commit', never 'Update
  branch'".
- The reconciliation outcome (4g), suggestion triage counts, `## Also Noticed` items, waived or
  unmet gates, and every skipped candidate with its reason.
- A full explanation for each blocked challenge, its checkpoint file and how to resume.
- Saga progress for every affected saga, and total stats.

When each PR lands, whichever session observes it runs
[challenge workflow](../../references/challenge-workflow.md) §7.
