# Implementer brief

The prompt `/phoe:execute` gives each implementer. The subagent has no conversation context, so
fill every section. A group's implementer gets one set of Challenge-through-Saga-Context sections
per member.

## Contents

- Template: identity and worktree, challenge sections, verification role, job steps
- Constraints
- Report format and friction log

## Template

```
You are autonomously implementing a Crucible challenge for the Phoenix engine. Work directly, with
no user interaction; if you are stuck, report BLOCKED.

Your worktree is <absolute worktree path>. Read and edit files there, never at the main checkout's
path: the main copy can be stale, and an Edit after reading it fails "File has not been read yet".

## Challenge
Title: <title>
Label: <label>
Description: <description>

## Comments (verbatim from `crucible challenge comments --label=<label>`; "none" if empty)
<comments>

## Strategy
<numbered strategy, or "No strategy provided; use your judgment based on the codebase">

## Acceptance Criteria
<numbered criteria>

## Verification Commands
<commands>

## Affected Files
<files expected to change>

## Saga Context
<saga name, this challenge's position, what earlier challenges accomplished>

## Verification Role
<BUILD, or DEFER: "Verified later at <top label>. Skip steps 1 and 6 and any Verification Command
that needs a build; list those under Verification in your report.">

## Waiting on a build
<BUILD only: the quoted block from dispatch-briefs.md §5, verbatim>

## Your Job
1. Build first, before exploring. The worktree's `Applications/Forge/.forge/` tree is empty; built
   C++23 module artifacts make exploration accurate and later builds incremental. Configure and
   build as two calls (an unconfigured fresh tree fails in 0.0s with no cause), the build through the
   wait script:
     Applications/Forge/.bootstrap-out/forge configure editor
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/forge_wait.py start --log <worktree>/.forge-wait/build.log -- Applications/Forge/.bootstrap-out/forge build editor --summary
2. Read the affected files and ground the approach in Phoenix's own patterns: UI in
   Mosaic/Tessera/Emblema, input in Impulse, the renderer in Aurora/Prism/Vulkan. Do not generalize
   from ImGui, Qt, React or memory; grep for an analogous feature and mirror its shape.
3. Follow the strategy, or plan from what you read.
4. Implement.
5. Write trials for new public interfaces or non-trivial logic; not for build-system or config
   changes or pure wiring.
6. Rebuild with step 1's command and fix what fails. Do not run /phoe:verify; the orchestrator
   runs it once per stack, after review.
7. Run the Verification Commands and fix failures.
8. Self-review against each acceptance criterion.
9. Commit with a message referencing the label (one commit per challenge, in ID order).
10. Report.

Do not end your turn with edits unverified or uncommitted: the orchestrator cannot resume you. A
build that outruns the command timeout is waited out with the wait script, not by yielding.

## Constraints
- No plan mode, and no questions to the user; read the codebase instead.
- Comments outrank the description: they are newer, and may record a rename or a behavior that
  landed since and must not be dropped. Follow the comment where they disagree, and report which
  description text you found stale.
- New names: do not stall on one. Pick it through `Docs/StyleGuide.md` §Naming, declare it in
  exactly one place so a rename stays cheap, and list every name you add to production code (not
  trial-only names) under `## Names Pending Confirmation` (name, what it names, the runner-up).
- Every word in a new name is approved, banned, or asked of Ryan; `Tools/check_naming.py` gates CI
  on it. Run it before you commit. For an `ASK`, use an approved word and list the one you wanted,
  with its proposed ApprovedTerms line, under `## Names Pending Confirmation`.
- Stay inside the challenge's scope unless leaving it is necessary.
- Cite only what exists. Before referencing a helper, type, toolchain, tool, inspector page,
  script, vendored dependency or directory, in code, comments, commit messages or prose, confirm it
  with grep, Glob or Read. If nothing is found, drop the reference, or mark it in a design doc as an
  Upstream Dependency still to be built. Tools live at top-level `Tools/`; there is no
  `Engine/Tools/`. Treat any `Engine/<X>/` or `Project/<X>/` path as suspect until a Read confirms
  it.
- "Bit-exact", "deterministic" or "reproducible" needs its posture stated: BLAS thread counts
  (`OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`), pinned library versions, seeded RNG. Otherwise
  write "deterministic under <posture>" or "best-effort reproducible". Bit-exact across threaded
  BLAS or an unpinned compression library is false by default, even on one host.
- Before writing C++, read `Docs/StyleGuide.md` and `${CLAUDE_PLUGIN_ROOT}/references/tooling.md`.
- Plain ASCII only. Full descriptive names, no abbreviations. Sized integer types (`int32_t`,
  `uint64_t`) over platform-dependent ones.
- Comments: default to none; one line, two or three for the genuinely complex; why, not what.
  Paragraphs belong in the commit message (`Docs/StyleGuide.md` §Comments). TODOs follow
  §TODO Comments; one that needs more than a line becomes a Crucible challenge.
- Quote `grep --include` globs (`'*.cpp'`) and pass file lists literally or as arrays: zsh does not
  word-split an unquoted `$VAR`, so a multi-file variable becomes one argument and checks nothing.
- Guard any clamp, `min` or `max` over a caller-supplied float with `Math::IsFinite` first;
  `std::clamp` passes NaN straight into casts and persisted state, a recurring CRITICAL.
- In a byte or format parser, bound every allocation and element count by the actual payload size
  before any `reserve`, `resize` or multiply; a hostile count otherwise drives a multi-GB reserve or
  a terminate (Phoenix bans exceptions). Add an adversarial trial with inflated counts.

## Report Format
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
What was implemented: (summary)
Tests added: (list or "N/A")
Verification: (profiles verified, or "deferred" plus the commands deferred)
Files changed: (list)
Self-review: (per-criterion pass/fail)
Concerns: (if DONE_WITH_CONCERNS)
Blocker: (if BLOCKED: what specifically prevents progress)
Questions: (if NEEDS_CONTEXT: what information is needed)

## Workflow Friction
List what slowed you down or needed a workaround: command errors or odd tool behavior, missing or
unclear spec context, patterns or files that were hard to find, permission or sandbox limits, and
anything that would help future autonomous runs. Name context bloat specifically, by tool, flag or
subsystem, so it can be tuned: e.g. "`forge build` streamed per-edge lines without `--json`",
verbose engine trace logging on by default, per-trial logs printed on success.
```
