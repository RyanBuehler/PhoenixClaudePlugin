# Dispatch briefs

What a `/phoe` workflow hands a subagent, kept here once for `/phoe:implement`, `/phoe:bugfix` and
`/phoe:execute`. Read §1-§4 and §7 before a review, §5 before dispatching anything that builds, §6
before acting on findings.

Most failure modes here fail toward a **false clean**: a reviewer that cannot find something
reports it absent, and that conclusion reaches the PR body.

## Contents

1. Dispatch mode: who gets write access
2. Assembling a review brief
3. Review dispatch preamble (pasted verbatim)
4. Reviewer prompts: spec, quality, adversarial
5. Waiting on a build
6. Acting on review findings
7. The review gate

## 1. Dispatch mode: who gets write access

Dispatch every reviewer as `Explore`, with the absolute path of the worktree under review and the
read-only clause below. Use the reviewer prompts in §4, not the `phoe:invoke-*` agent types:

- The specialists that author changes (`invoke-build-engineer`, `invoke-perf-agent`,
  `invoke-platform-agent`, `invoke-shader-expert`, `invoke-vulkan-agent`; check the agent file)
  carry `isolation: worktree`, so they start in a fresh worktree off `main` and cannot see the
  branch under review.
- `invoke-code-reviewer` and `invoke-spec-reviewer` carry no `isolation` key and the same tools as
  `Explore` (Read, Grep, Glob, Bash). Every option has Bash, which writes, so a reviewer is kept
  read-only by the clause, not by its tool list. Judge an agent by its tools, not its description.

A reviewer that writes in a live worktree corrupts it: one reverted its own probe with a checkout
and destroyed its author's uncommitted trial, and left a build that broke the shared build tree for
the next two builds. Read-only review costs nothing in quality. Include this clause in every review
dispatch:

> You are read-only. Do not build, configure, `git checkout`, `git stash`, `git restore`, or write
> any file in this worktree — its author has uncommitted work here and a build of your own would
> corrupt the shared build tree. Report what you find; change nothing.

**Test writing is the exception.** It needs to write, so dispatch `invoke-test-engineer` with the
absolute worktree path. Keep it visibly separate from review dispatches, and never run it alongside
a review of the same tree.

## 2. Assembling a review brief

**Freeze the range.** Commit first, then resolve both ends at dispatch time:

```bash
REVIEW_SHA=$(git -C <worktree> rev-parse HEAD)
REVIEW_BASE=$(git -C <worktree> merge-base origin/main HEAD)
```

A stack layer's `REVIEW_BASE` is its recorded parent SHA, so the review covers only that layer.
With origin unreachable, use `merge-base main HEAD` and say the base is local `main`. Never
transcribe a hash or extend a short one by hand: a near-miss makes every range command fail with
`Invalid revision range`, which reads as a broken worktree; where the reviewer can resolve a ref
itself, hand it the ref instead. Re-resolve both after every fix commit.
Never hand a reviewer "the staged diff"; the index moves while you work.

**Ship the contract verbatim.** Interpolate the whole `"$CRUCIBLE" <kind> show --label=<LABEL>`
output under `## Challenge Contract (verbatim from Crucible)` (`## Bug Contract` for a bug). The
reviewer cannot reach Crucible, and without the exact criteria it invents a contract from the code
and blocks on it.

**Generate the file list from the range**, `git diff --name-only "$REVIEW_BASE".."$REVIEW_SHA"`,
never from the contract's `Files` field, which was written before the work and goes stale. Pass the
affected/context distinction through:

> `affected_files` lists what this change was expected to modify — an entry the diff leaves untouched
> is a question worth raising. Entries under `Context:` in references are background only; they are
> *expected* to be unchanged. Older challenges predate this split and may mix the two — when in
> doubt, trust the generated file list above, not the contract.

**State the build state.** Name the warm build directory (e.g. `Applications/Forge/.forge/`) and
whether a build has run on this branch; the profile the shared tree is configured for (editor and
forge share one tree, and a tree warm for the other fails at link like a real defect); and which
profiles were verified, or that verify runs after review, so its absence is not a finding. A profile
the change edits must be in the verified set (`/phoe:verify` §2a).

**Resolve every design-doc reference** the contract or code cites (`Docs/Cortex_DD.md §4.6`): confirm
the file and section exist in this worktree, and say so in the brief when one is absent, so no
finding rests on a section that was never there.

**Carry the evidence.** Report [targeted compilation](targeted-compilation.md) results with their
exact TU and profile, apart from verified profiles. Each [negative control](negative-controls.md)
witness gives its claim and path, mutation, executed case, intended failure, successful build and
verified restoration.

## 3. Review dispatch preamble

Paste this verbatim into every reviewer prompt, with the resolved values for `<BASE>`/`<SHA>` and
`<PLUGIN_ROOT>` (the plugin directory). Explore reviewers do not receive the core rules, so the
preamble has them read the file.

> **Reading the change.** You are reviewing the frozen range `<BASE>..<SHA>`. It is immutable; the
> working tree is not. This checkout is shared, the author may still be working and siblings write
> to it, so files read in place can change between two of your own calls.
>
> - Get the map with `git diff --name-only <BASE>..<SHA>`. `git diff --stat` elides long paths with a
>   leading ellipsis, and an elided path matches nothing as a pathspec; if you want the stat, use
>   `--stat=200`.
> - Read content from the commit: `git show <SHA>:<path>` and `git diff <BASE>..<SHA> -- <path>`, one
>   file at a time. Do not dump a whole diff; past about 30 KB it overflows the output caps. Reading
>   uncommitted work is a deliberate exception you name in your report.
> - At the start and again before reporting, check `git rev-parse HEAD` equals `<SHA>` and
>   `git status --porcelain` is empty. A commit past the range leaves a clean tree, so check both. If
>   either fails, say so and mark which findings the newer work may address.
> - `Invalid revision range` means a bad argument, not a broken repository. Re-resolve and retry.
>
> **The rules.** Before judging, read `<PLUGIN_ROOT>/references/core-rules.md`. A change that breaks
> its §Codebase rules is a finding. Every word in a new name is approved (ApprovedTerms, a Lexicon
> heading, a module name), banned (a Lexicon `Not:` line), or asked of Ryan; `Tools/check_naming.py`
> gates CI on it.
>
> **Where things live.** The editor is `Applications/Editor/`, not under the engine tree; engine
> modules are `Engine/Modules/<Group>/<Module>/`. Scope every search to the worktree root you were
> given: `.claude/worktrees/`, `.forge*/` and `.bootstrap-out/` hold near-identical copies of the
> sources. Prefer `git grep` (tracked files in this tree); with `grep -r` or `find`, exclude all three.
>
> **Empty output is not evidence.** Each of these looks exactly like a genuine negative:
>
> 1. A pathspec matching nothing makes `git diff`/`git show` exit 0 silently; `git grep` exits 1 for
>    both a dead pathspec and an absent pattern.
> 2. A shell trap (below) aborts the command before it runs.
> 3. A misspelled revision in `git grep <sha>` prints nothing and exits 0.
> 4. A pipe replaces the exit status (`git grep ... | cat` exits 0). Run absence checks unpiped.
> 5. A no-match exits 1, so `git grep A && git grep B` never runs B. Chain with `;`.
> 6. `git grep -r` is not an option; piped to `grep -c` it prints a convincing `0`, and `-c` over
>    several files prints per-file counts.
>
> Before claiming anything is missing, absent or unreferenced, confirm it with a second command of a
> different shape, and state which tree you searched.
>
> **Shell traps.**
>
> - Under zsh (Linux hosts), an unquoted glob that matches nothing aborts the whole line
>   (`--include=*.h`); quote it (`--include='*.h'`). A word starting with `=` triggers EQUALS
>   expansion (`echo ====` dies); quote it.
> - A `git grep` flag after the pattern is parsed as a revision (`-A 2` → `unable to resolve
>   revision`). Put flags before the pattern.
> - `git grep` has no `--include`; give a pathspec after `--`.
> - A pattern like `->Method` needs quoting (an unquoted `>` redirects and creates a file) and `-e`
>   (a leading `-` reads as a flag): `git grep -n -e '->Method' -- '<pathspec>'`.
>
> **Verify every citation.** Each path and symbol in a finding must resolve against the reviewed
> commit (`git show <SHA>:<path>`, `git grep`). Unresolvable citations are the most reported defect in
> review output, and the next agent acts on them. Never carry a path over from a stat summary, a
> contract's file list or memory.
>
> **Lint runs in verify** (`forge lint`: clang-tidy over the changed surface, the module-import graph
> included), before or after review as the brief states. Do not re-adjudicate include/import hygiene
> or punt to `invoke-lint-agent` without a concrete contradiction in the diff. Caveats: a header
> reached only transitively is reported `uncovered` while the summary still says "N files clean", so
> header-only code may have had no analysis; and the compile database is profile-scoped, so a diff
> spanning two profiles needs two lint runs.
>
> **Ask what a green suite would still allow.** Build and test have caught none of the blocking
> findings in these reviews. For each invariant the change claims, name the production mutation that
> would leave every trial green, concretely enough for the next agent to arm it. Where a case has no
> such mutation, call it unpinned.
>
> **Distinguish ran from deduced.** CONFIRMED means you ran it; otherwise label the conclusion
> deduced.
>
> **The brief is a claim.** Its statements about the code are often written from memory. If your
> reading disagrees, trust your reading and name the sentence you contradict.

## 4. Reviewer prompts

Each prompt is the opening below, then the contract (§2), the preamble (§3), the read-only clause
(§1) and this closing line:

> End your report with a `## Workflow Friction` section listing anything that made this review
> harder than it should have been — missing context, ambiguous spec, undocumented convention,
> tooling gaps — or the single word `none` if nothing applied.

**Spec reviewer.**

> Review spec compliance for <kind> `<label>`: every acceptance criterion met, nothing extra beyond
> the contract. Give a pass/fail line per criterion with evidence. Files changed (generated from the
> range): <list>.

**Quality reviewer.** For a bug, add the bracketed sentence.

> Review the change on this branch. Focus on correctness, safety, modern C++23 opportunities,
> performance, and project convention compliance. [Verify the fix addresses the root cause and does
> not introduce regressions.] Report findings using CRITICAL/WARNING/SUGGESTION/NOTE severity levels.

**Adversarial reviewer.** A fresh agent with no context shared with the quality reviewer.

> Adversarially review the change on <kind> `<label>`. Attack it; do not validate it. A quality
> review runs separately — do not duplicate it. Hunt for:
>
> - Edge cases: empty and max-size input, unicode, negative values, NaN, integer overflow,
>   signed/unsigned mismatch, off-by-one at boundaries.
> - Concurrency hazards: races, reentrancy, ordering assumptions across threads or subsystems,
>   lifetime invariants the type system does not enforce.
> - Silent failure: paths that swallow errors, no-op on the unexpected branch, or skip Scribe logging.
> - Hidden coupling: state shared across modules, ownership confusion, call-order or initialization
>   assumptions.
> - Performance under realistic load: allocation in hot paths, O(n²) at expected n, lock contention,
>   cache-hostile access.
> - Spec gaps: criteria that pass for the easy case and fail for plausible variations. If the spec
>   is the weak link, say so.
> - Trials that cannot fail: beyond the preamble's mutation question, two cases killed by the same
>   mutation (one is redundant), and fixtures whose shape differs from what the code actually runs on
>   (trials can agree with each other while every shipped row is wrong).
>
> Report only real failure modes, not style, with CRITICAL/WARNING/SUGGESTION/NOTE severity. A clean
> adversarial pass is a valid result; say so explicitly.

## 5. Waiting on a build

A cold build, verify or bootstrap can outlive the ten-minute command timeout, and every look at a
running build's log costs a full-context request (re-reading logs once took 46% of subagent tokens).
Paste this into any brief whose agent builds:

> Run every long Forge command — `bootstrap.py`, `forge build`, `forge verify` — through the
> plugin's wait script, as a **foreground** Bash call with `timeout: 600000`:
>
> ```bash
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/forge_wait.py start --log <worktree>/.forge-wait/verify.log -- Applications/Forge/.bootstrap-out/forge verify editor --summary
> ```
>
> (`${CLAUDE_PLUGIN_ROOT}` is substituted only in skill text; if your shell sees it empty, find the
> plugin under `~/.claude/plugins/cache/*/phoe/*/`.) It runs the command detached, blocks for up to
> 9.5 minutes, then prints the outcome once: `exited <code>` with the log (head, tail and every
> `FAILED` line when long), or `still running` with the `wait --log …` command to call next. Call
> that, in the foreground, until it reports an exit. Do not read or `tail` the log meanwhile and do
> not sleep between calls.
>
> Exit 124 means still running, not failed; 125 means the command died without a status. On an
> exit, read the phase lines, not the exit code alone: a `FAILED` build beside a passing test tally
> means the trials ran against the previous binary. Keep the log in your own worktree;
> `.forge-wait/` is gitignored, and `start` refuses a log a live run still owns.
>
> Do not edit while a bootstrap runs: it bakes the on-disk tree into the binary it produces. If your
> change touches what the bootstrap embeds (the PhoenixPy cook or `bootstrap.py`'s shared modules),
> re-bootstrap; otherwise `forge build` keeps emitting generated sources from the old emitter, and
> no clean fixes it.

Do not prescribe `nohup … &`, PID files, `until`/`for` polling loops or process-name matching: a
match on the compiler or builder name catches every sibling's build or silently matches nothing.

## 6. Acting on review findings

Whoever fixes findings, whether you or a fix subagent, follows these rules. Give a fix subagent this
instruction verbatim:

> Fix exactly these findings: `<list>`. Do not refactor, rename, or touch anything the findings do
> not name. If you spot another problem, describe it under an `## Also Noticed` heading in your
> report — do not fix it. End with a `## Workflow Friction` section, or `none`.

- **Resolve every cited path and symbol first.** Findings often cite paths that do not exist while
  being otherwise right (stat elision, stale file lists, the editor/engine tree confusion). Say so,
  find the real target, and never fix the nearest plausible thing.
- **Re-check a finding's factual claims** before acting, and test a reviewer's predicted consequence
  before writing it into a commit message: a correct mechanism does not make the inferred failure
  real.
- **Fix only the named findings.** An unvetted improvement reopens the gate. Read `## Also Noticed`
  before the fix report; it has carried a run's most valuable observation.
- **Keep passes narrow.** Split a large finding set into two or three passes, each re-reviewed; one
  broad pass touched five files outside the diff and introduced three defects there.
- **Prefer deleting or narrowing an overreaching claim to writing a replacement**, especially in
  prose: a deletion cannot introduce a false claim.
- **Re-arm the negative control after the last edit**; one run from before it proves nothing.
- **Check the directions, not just the fixes.** Verify a design justification before briefing it
  ("the API doesn't allow X": grep the API), and settle contradicting reviewers from the source, not
  by vote. When three rounds in a row each close one finding and open another, the shape is wrong:
  stop adding guards and ask what object the obligations want to be.

## 7. The review gate

- **Pass condition.** Every dispatched reviewer has returned and zero CRITICAL and zero WARNING
  findings remain. WARNING blocks like CRITICAL.
- **Failed dispatch.** A return with no tool use, no verdict, or a fragment left by an overload
  (529) or rate limit (429) is not a pass. Re-dispatch it once with the same prompt rather than a
  smaller model, and do not start a deciding round near a usage limit.
- **After a fix**, commit, re-resolve the range (§2), and re-run every reviewer: a fix can introduce
  new defects of any class.
- **Convergence.** Judge only once every reviewer has returned (two early returns once looked like
  8 → 3 blocking before the adversarial pass added 8). Compare the blocking count (CRITICAL plus
  WARNING) to the previous round's. Converging (fewer, and no new blocker on surface no round asked
  for) earns another narrow pass; findings against surface a previous round demanded are expected,
  not thrashing. Stalled or regressing means stop. Five rounds is the backstop.
- **When review cannot run** (the Agent tool is forbidden, or dispatches keep dying), the gate is
  unmet, not passed. Say so in the report and the PR body, naming the gate; substitute mutation
  testing with armed and reverted negative controls, one defect at a time, as a stated stand-in; and
  leave the item short of `review`.
- **SUGGESTION and NOTE** do not block. The skill says how they are handled.
