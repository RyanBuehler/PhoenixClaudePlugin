# Dispatch Briefs

Every `/phoe` workflow that hands work to a subagent assembles a **brief**: the contract, the
range under review, the state of the tree, and a preamble of environment rules. This file is the
single source for those blocks. `/phoe:implement`, `/phoe:bugfix` and `/phoe:execute` all point
here rather than each carrying its own copy — three copies drifted apart once and every drift
shipped as a wrong instruction in a live dispatch.

Each failure mode below was reported by subagents in the field, and they share a direction:
**they fail toward a false clean.** A reviewer that cannot find something reports it as absent, and
that conclusion reaches the PR body.

## 1. Dispatch mode — who gets write tools

**Review and adversarial-review dispatches are read-only.** Dispatch them as `Explore` (or any
read-only agent type), and pass the absolute path of the live worktree so they can see uncommitted
code.

The two halves of that sentence are both load-bearing, and the obvious fixes for each break the
other:

- **Most `phoe:invoke-*` specialists carry `isolation: worktree`** in their frontmatter
  (`invoke-test-engineer`, `invoke-build-engineer`, `invoke-lint-agent`, and the rest — check the
  agent file before assuming), so the harness drops them in a *fresh* tree branched from `main`,
  without the work under review. That is why a dispatch must name the live worktree rather than rely
  on the agent finding it.
- **"Read-only" in an agent's description is not read-only in its tools.**
  `invoke-code-reviewer` and `invoke-spec-reviewer` carry no `isolation` key — they land in the
  caller's tree — and both list `Bash`, which writes. `invoke-spec-reviewer` even describes itself as
  "read-only analysis". Judge a dispatch by its tool list, not its prose.
- A reviewer with write tools pointed at a tree its author is still working in **will corrupt it.**
  One such reviewer appended a probe trial to a trials file, reverted it with a checkout of that
  path, and destroyed the orchestrator's own uncommitted trial in the same file. It also left an
  orphaned build running against the shared build tree, which produced clang internal compiler
  errors in unrelated core modules on the orchestrator's next two builds — failures that read as a
  broken toolchain rather than as write contention.

Read-only dispatch cost nothing in review quality: the first pass run this way still found a real
defect in the previous pass's fix. Do not re-introduce a write-capable reviewer to solve the
isolation problem — pass the path, drop the tools.

Include this line in every review dispatch:

> You are read-only. Do not build, configure, `git checkout`, `git stash`, `git restore`, or write
> any file in this worktree — its author has uncommitted work here and a build of your own would
> corrupt the shared build tree. Report what you find; change nothing.

**The test-writing dispatch is the exception.** `invoke-test-engineer` genuinely needs to write, so
it is dispatched write-capable into the worktree. Keep that dispatch visibly separate from the
review dispatches so the read-only rule is not read as applying to it — and do not run it
concurrently with a review of the same tree.

## 2. Assembling the brief

**Resolve every commit hash at dispatch time. Never transcribe one.**

```bash
REVIEW_SHA=$(git rev-parse HEAD)
REVIEW_BASE=$(git merge-base origin/main HEAD)   # the branch's real fork point, never a literal `main`
```

A hash copied out of earlier output, or a short hash extended by hand, produces a value that shares
a prefix with the real head and differs after it. Every range command then aborts with
`fatal: Invalid revision range`, which reads to a reviewer as a broken worktree, not a bad argument
— two reviewers on one round each spent two round trips recovering the true hash. Where the reviewer
can resolve the reference itself, hand it the reference rather than the literal hash, so a stale
value cannot survive into the prompt at all.

**Generate the file list from the range, never from the challenge contract.**

```bash
git diff --name-only "$REVIEW_BASE".."$REVIEW_SHA"
```

A contract's `Files` list is a hint written before the work, and it goes stale. Transcribing it into
a brief is how a reviewer came to read sixteen hundred lines of a file the commit never touched.

**Pass the affected/context distinction through.** Challenges authored under the current
`/phoe:plan` guidance put only files the change is *expected to modify* in `affected_files`, and put
files that are merely background in `references`, prefixed `Context:`. Say so in the brief, so the
reviewer knows how to read a mismatch:

> `affected_files` lists what this change was expected to modify — an entry the diff leaves untouched
> is a question worth raising. Entries under `Context:` in references are background only; they are
> *expected* to be unchanged. Older challenges predate this split and may mix the two — when in
> doubt, trust the generated file list above, not the contract.

**State the build state accurately.** The brief's build-state block must name:

- Which build directory is warm (e.g. `Applications/Forge/.forge/`) and whether a build has run on
  this branch — otherwise a reviewer reports a static-only review claiming no build tree exists.
- **The profile that shared build tree is currently configured for.** The editor and forge profiles
  share one tree; a tree warm for the other profile fails at link in a way that reads as a real
  defect in the diff.
- **Which profiles were actually verified** — and if the change edits a profile, that profile must
  appear in the verified set. One brief listed six profiles as verified while the commit edited six
  *other* profiles, none of which any listed verify touched. A reviewer taking that at face value
  concludes the change was validated. See `${CLAUDE_PLUGIN_ROOT}/commands/verify.md` for what one
  verify run does and does not cover.

**Resolve every design-doc reference the contract cites.** Confirm the file exists in *this*
worktree and that the cited section is present. If it is absent, say so explicitly in the prompt
("`Docs/ForgePlatformModel_DD.md` is referenced but absent from this worktree; do not weigh comments
against it") — reviewers have built headline findings on sections that were never there.

**Ship the contract verbatim.** Interpolate the whole `crucible challenge show` / `bug show` output
under a `## Challenge Contract (verbatim from Crucible)` heading. Do not summarize and do not
re-word acceptance criteria: their exact wording is what the reviewer judges scope against, and the
review gates block on CRITICAL/WARNING — a reviewer that cannot read the criteria invents the
contract from the code and then blocks on it.

## 3. Review dispatch preamble

Paste the block below **verbatim** into every reviewer prompt, substituting the resolved
`REVIEW_BASE`/`REVIEW_SHA` values for `<BASE>`/`<SHA>`.

> **Reading the change.** You are reviewing a **frozen commit range**, `<BASE>..<SHA>`. It is
> immutable for the life of your review; the working tree is not.
>
> Get the map by name, not by stat:
>
> ```bash
> git diff --name-only <BASE>..<SHA>
> ```
>
> `git diff --stat` abbreviates long paths with a leading ellipsis, and **an abbreviated path is not
> a real path** — feeding one back as a pathspec matches nothing. If you want the stat summary,
> request it with an explicit width so nothing is elided: `git diff --stat=200 <BASE>..<SHA>`.
>
> Then read each file **out of the frozen commit**, not from the working tree:
>
> ```bash
> git show <SHA>:<path>                # the reviewed content
> git diff <BASE>..<SHA> -- <path>     # the delta for one file
> ```
>
> Reading in place silently mixes reviewed and unreviewed content. This checkout is shared — the
> author is often still working and sibling agents write to it. Three separate reviews were bitten:
> one saw an implementation file go from 118 lines to 111 between two of its own tool calls; another
> read the same lines of a design document twice and got different text. If you genuinely need to
> see uncommitted work, say so as a deliberate exception and name the reason in your report.
>
> **Check that the range is still the tip, at both ends of your pass:**
>
> ```bash
> git rev-parse HEAD        # must equal <SHA>
> git status --porcelain    # must be empty
> ```
>
> Run both at the start and again before you report. `git status` alone misses the common failure:
> the author **commits** past the range mid-review, leaving a clean tree and a moved HEAD. If either
> check fails, say so and mark which findings the newer work may already address.
>
> Do not pipe a whole diff. A whole-diff dump on a 30 KB+ change overflows the Bash output cap,
> spills to a temp file, then overflows the Read cap.
>
> An `Invalid revision range` error means a **bad argument** — a mistyped or stale hash — not a
> broken worktree or repository. Re-resolve the reference and retry; do not report the tree as
> broken.
>
> **Where things live.** The editor lives under `Applications/Editor/`, **not** under the engine
> modules tree; engine modules live under `Engine/Modules/<Group>/<Module>/`. Assuming otherwise
> returned three empty scoped diffs in a row for one reviewer — indistinguishable from "no changes
> here."
>
> **Where to search.** This repository holds many sibling worktrees under `.claude/worktrees/` and
> build trees under `.forge*/` and `.bootstrap-out/`, all carrying near-identical copies of the same
> sources. Scope every search to the worktree root you were given. Prefer `git grep`, which searches
> only tracked files in the current tree. If you use `grep -r`/`find`, exclude `.forge*/`,
> `.bootstrap-out/` and `.claude/worktrees/` — a generated `compile_commands.json` alone can exceed
> the output cap.
>
> **Empty output is not evidence.** Seven different mechanisms produce an empty result — or a
> plausible `0` — that looks exactly like a genuine negative:
>
> 1. A pathspec that matches nothing makes `git diff`/`git show` **exit 0 and print nothing** —
>    identical to an unchanged file. `git grep` exits 1 instead, but that does **not** disambiguate
>    anything: a dead pathspec and a genuinely absent pattern both give exit 1 with no output and no
>    diagnostic. A `git grep` miss is never by itself evidence of absence.
> 2. A shell trap (below) can abort the command before it runs.
> 3. The background-session command guard can refuse the command outright.
> 4. **A misspelled revision is swallowed.** `git grep <typo-sha> …` prints nothing and exits 0
>    with no diagnostic.
> 5. **A pipe replaces the exit status.** `git grep -n Foo <sha> | cat` reports `cat`'s exit 0,
>    destroying the signal the check rests on. Run absence checks unpiped.
> 6. **An `&&` chain drops its second command.** A no-match exits 1, so `git grep A && git grep B`
>    never runs B, and B's silence reads as absence. Chain with `;`.
> 7. **`git grep -r`** is not an option at all; piped into `grep -c` it prints a convincing `0`, and
>    `-c` over several files prints per-file counts rather than one number.
>
> So: **before claiming anything is missing, absent, or unreferenced, confirm it with a second
> command of a different shape**, and state which tree you searched.
>
> **The command guard.** In a background session a guard inspects the *whole command line* and can
> refuse it. It does not require a pipe, an and-chain or a redirect — plain single commands have been
> refused: a bare diff limited to one module's code directory, and a bare search with one pathspec.
> It also fires on text in a downstream filter that the `git` command never receives, which shows it
> scans the line rather than the git arguments. A refusal prints an error and no results; read the
> error, and never record a refused command's empty output as a negative.
>
> It refuses two independent things, and its message names neither:
>
> - **A path segment**, which appears in every engine module path here — so it fires on the most
>   common command shape in a review. Escapes, most reliable first: **truncate the path above the
>   offending segment** and filter afterwards (`-- 'Engine/Modules/Rendering/Mirage'`); quote the
>   pathspec as a glob (`-- '*/Mirage/*'`); reduce several pathspecs to one. Quoting alone does not
>   always clear it, and `git show <SHA>:<path>` is refused *intermittently* — the same call can run
>   in one batch and be refused in the next, so keep `sed -n` on an absolute path as a fallback.
> - **A command shape**, regardless of path: `for`/`while` loops, heredocs (including ones whose body
>   merely contains `git` or a brace), `;`- and `&&`-chains, process substitution in anything naming
>   git, and `nohup … &`. Use one plain command per call, or run a script from outside the repository
>   by absolute path.
>
> Every refusal blames git, a worktree escape, or a redirect that is not in the command, so it never
> names the real trigger. A workaround that broadens a pathspec **changes what you searched** — say
> which shape you ran when a finding rests on it.
>
> **Shell traps.** Bash here runs under **zsh**, and each of these has cost a reviewer a round trip:
>
> - An **unquoted glob that matches nothing aborts the entire and-chain before anything runs**
>   (`--include=*.h` → `no matches found`), and the result reads as a search miss. Quote every
>   glob-bearing flag: `--include='*.h'`, or use `git grep -n <pattern> -- '<pathspec>'`.
> - **A word starting with `=` triggers EQUALS expansion.** `echo ==== RESULT ====` dies with
>   `=== not found`, discarding output you already paid for. Quote it: `echo '==== RESULT ===='`.
> - **A context flag placed after a `git grep` pattern is parsed as a revision**:
>   `git grep -n Foo -A 2` fails with `fatal: unable to resolve revision: -A`, which reads like a bad
>   commit. Put every flag *before* the pattern.
> - **`git grep` rejects `--include`** (`error: unknown option 'include=*.cpp'`). Use a pathspec after
>   `--` instead.
> - **Two separate hazards in one pattern like `->Method`.** An unquoted `>` is read by zsh as a
>   redirection and silently creates a file — **quoting** fixes that. A leading `-` is parsed by the
>   command as a flag — only **`-e`** fixes that. A pattern with both needs both:
>   `git grep -n -e '->Method' -- '<pathspec>'`.
>
> **Verify every citation before you report it.** Each path and symbol you name in a finding must
> resolve against the reviewed commit — `git show <SHA>:<path>` for a path, `git grep` for a symbol.
> Citations that do not exist are the single most reported defect in review output, and the cost
> lands on the next agent, which acts on them. Do not carry a path over from a stat summary, a
> contract's file list, or memory without resolving it first.
>
> **Lint already ran** as part of this branch's verify (`forge lint`, clang-tidy over the changed
> surface, module-import graph included) and passed. Do not re-adjudicate include/import hygiene or
> punt to `invoke-lint-agent` unless you see a concrete contradiction in the diff. Two caveats: a
> header reached only transitively is reported `uncovered — no TU in compile_commands.json includes
> it` **while the summary still says "N files clean"**, so header-only code may have had no analysis
> at all; and the compile database is profile-scoped, so a diff spanning two profiles needs the union
> of two lint runs.
>
> **Ask what a green suite would still allow.** Build and test have caught none of the blocking
> findings here, so another reading of the diff is not this review's highest-value output. For each
> invariant the change claims, name **the production mutation that would leave every trial green**,
> concretely enough for the next agent to arm it. Trials that pass with the code they name deleted
> have shipped twice. Where a case has no such mutation, say the case is unpinned.
>
> **Distinguish what you ran from what you deduced.** Being read-only, you often cannot run the
> decisive experiment. Say so and label the conclusion deduced; CONFIRMED means you ran it.
>
> **The brief itself is a claim.** Its statements about what the code does are often written from
> memory, and reviewers have disproved several. If your reading disagrees, trust your reading and
> name the sentence you are contradicting.

## 4. Implementer dispatch — waiting on a build

Do not tell an implementer to "run the build in the foreground and do not yield." A full cold build
here exceeds the ten-minute command timeout, so the harness backgrounds it regardless. The
instruction writes a contract the environment cannot honor, and it breaks silently: the agent
believes it is waiting and is not.

**Do not prescribe the `nohup` + PID-file recipe this section used to carry.** The command guard
refuses all three of its parts — `nohup … > log 2>&1 &`, the `echo $! > …` capture, and the
`for _ in $(seq 1 16)` poll — so agents handed it stranded turns mid-build with edits uncommitted.
Never prescribe a shape that has not been run in an isolated agent.

Give the implementer a wait mechanism that survives the guard:

> Your build will outlive the command timeout, so run it as a **single plain command with the
> harness's background mode** (`run_in_background: true`) — not `nohup`, not `&`, not a compound
> command. The harness notifies you when it exits; that is the only wait primitive both allowed here
> and honest.
>
> ```bash
> Applications/Forge/.bootstrap-out/forge build <profile>    # run_in_background: true
> ```
>
> If you must poll instead, four things are true and each has cost an agent a run:
>
> - **A foreground `sleep` is blocked, and a backgrounded one returns immediately.** An
>   `until …; do sleep; done` loop launched in the background is reaped and reports success with
>   empty output — indistinguishable from the condition being met.
> - **A loop is refused by the guard** wherever it appears inline. If you need one, run it from a
>   script *outside the repository* by absolute path.
> - **Watch the log file, not a pipe.** Piping a backgrounded build through `tail` buffers and shows
>   nothing for minutes. Redirect to a file and read it as `tr '\r' '\n' | tail` — Forge writes its
>   progress heartbeat with carriage returns, so a plain `tail` shows one stale line forever on a
>   healthy build, which looks exactly like a wedged one.
> - **Anchor any `Monitor` pattern.** Verify's phase labels collide (`^(Format|Lint|Test) ` matches
>   the earlier `Test tools` line; `violations` matches `no violations`), and an unanchored pattern
>   exits the wait early on its own grep.
>
> Do not wait by matching process command lines. Two shapes of that loop are broken:
>
> - **Unscoped** — a bare match on the compiler or builder name returned 106 hits from sibling agents
>   building concurrently, so the wait never finishes.
> - **Scoped the obvious way** — a pattern that places the worktree path next to the compiler name
>   matches nothing, because the compiler binary appears on the command line *before* the include
>   flag that carries the worktree path. It silently matches zero processes and the wait returns
>   instantly, which looks exactly like a completed build.
>
> A watcher pattern that matches its own command line never exits, for the mirror-image reason.
> A `pkill -f` cleanup has the same two failure modes and a third: Forge's own command line is
> relative, so an absolute-path pattern matches nothing while exiting 0.
>
> A build that is still running is never a finished build. Confirm from the log's **terminal line**
> that the build reported a result — a build that outran your poll leaves the previous binary in
> place, so a trial run then reports the previous code's result.

**Two more things the implementer needs told, each of which has cost a full rebuild:**

- **Do not edit while a bootstrap is running.** It bakes the on-disk tree into the binary it
  produces, so an edit mid-bootstrap compiles a half-updated tree and can leave no `forge` binary
  and no useful diagnostic. The same ordering binds the orchestrator: dispatching an implementer
  whose first action is a build, before the bootstrap finishes, fails with `No such file or
  directory` and reads as a broken tree. Block until the binary exists.
- **Re-bootstrap when the change touches anything the bootstrap embeds** — the PhoenixPy cook and
  `bootstrap.py`'s other shared modules. Otherwise `forge build` succeeds while still emitting
  generated sources from the *old* emitter, and no clean fixes it.

## 5. Acting on review feedback

The agent receiving review findings verifies them before acting:

- **Resolve every cited path and symbol first.** Review findings routinely carry a path or symbol
  that does not exist while being otherwise correct — from stat-summary path elision, from a stale
  contract file list, or from the applications/engine tree confusion above. If a citation does not
  resolve, say so in your response and re-locate the real target before fixing anything; do not fix
  the nearest plausible thing.
- **Re-check a finding's factual claims.** One fix pass was built on a prior review's assertion that
  a function had no production consumer; a single search disproved it. The resulting rewording was
  harmless by luck — it could as easily have driven the fix the wrong way.
- **Fix only the named findings.** Report an unrelated problem under an `## Also Noticed` heading
  instead of fixing it — reviewers never vetted that surface, so an over-reaching pass re-opens the
  gate. Read that section **before** the fix report; it has carried a run's most valuable
  observation.
- **Keep a fix pass narrow.** One pass handed ten findings touched five files outside the original
  diff and introduced three new defects there. Split a large finding set into two or three passes,
  each re-reviewed: round-2 review repeatedly catches CRITICALs that the *fix* introduced.
- **Prefer deleting or narrowing an overreaching claim over writing a replacement**, especially in
  prose whose purpose is factual accuracy — two fix rounds each replaced a wrong statement with a
  new wrong one. A deletion cannot introduce a false claim.
- **Re-arm the negative control after your last edit.** A control run from before it proves nothing
  about what ships.
- **Test a reviewer's predicted consequence before writing it into a commit message.** A correctly
  identified mechanism does not make the inferred failure real; twice it was not.

## 6. When the review gate cannot run

The paired review is a blocking gate, and it has been silently unmet: four consecutive rounds
shipped on self-review alone because session instructions forbade the Agent tool. Never treat an
unavailable dispatch as a pass. When review dispatch is unavailable:

- Say so explicitly in the report and in the PR body: which gate did not run, and why.
- Substitute the closest thing a single agent can do — mutation testing with armed and reverted
  negative controls, one defect at a time — and report it as a substitute, not as the gate.
- Leave the challenge in a state that says the gate is outstanding rather than closing it.

**A partial reviewer output is a failed dispatch, never a clean pass.** Reviewers die mid-analysis
on API overload (529) and rate limits (429), leaving a plausible fragment that reads like a reviewer
which simply found little; re-dispatching after two such deaths is what found both BLOCKERs.
Re-dispatch rather than downgrading the model, and do not start a deciding round near a usage limit.

**Do not judge the convergence trend until every reviewer has returned.** Two of three round-2
reviews once looked like convergence (8 blocking → 3) before the adversarial pass landed 2 CRITICAL
and 6 WARNING. Judge on CRITICAL count plus total blocking count, and count findings against surface
a previous round *demanded* as expected, not as thrashing — otherwise every round that adds code
looks like a regression.
