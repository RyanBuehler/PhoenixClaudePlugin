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
> Run `git status --porcelain` once before you report. If the tree carries modifications, say so,
> and flag any finding that uncommitted work may already have addressed.
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
> **Empty output is not evidence.** Three different mechanisms produce empty output that looks
> exactly like a genuine negative result:
>
> 1. A pathspec that matches nothing makes `git diff`/`git show` **exit 0 and print nothing** —
>    identical to an unchanged file. `git grep` exits 1 instead, but that does **not** disambiguate
>    anything: a dead pathspec and a genuinely absent pattern both give exit 1 with no output and no
>    diagnostic. A `git grep` miss is never by itself evidence of absence.
> 2. A shell trap (below) can abort the command before it runs.
> 3. The background-session command guard can refuse the command outright.
>
> So: **before claiming anything is missing, absent, or unreferenced, confirm it with a second
> command of a different shape**, and state which tree you searched.
>
> **The command guard.** In a background session a guard inspects the *whole command line* and can
> refuse it. It does not require a pipe, an and-chain or a redirect — plain single commands have been
> refused: a bare diff limited to one module's code directory, and a bare search with one pathspec.
> It also fires on text in a downstream filter that the `git` command never receives, which shows it
> scans the line rather than the git arguments. A refusal prints an error and no results; read the
> error, and never record a refused command's empty output as a negative. Working shapes when a
> command is refused:
>
> - quote the pathspec as a glob — `git grep -n Foo -- '*/Widget/*'`
> - reduce to a single pathspec instead of several
> - truncate the path above the offending segment and filter the results afterwards
>
> Reading a prior revision of one file carries the same path and is refused the same way; prefer
> `git show <SHA>:<path>` over a piped form.
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
> punt to `invoke-lint-agent` unless you see a concrete contradiction in the diff.

## 4. Implementer dispatch — waiting on a build

Do not tell an implementer to "run the build in the foreground and do not yield." A full cold build
here exceeds the ten-minute command timeout, so the harness backgrounds it regardless. The
instruction writes a contract the environment cannot honor, and it breaks silently: the agent
believes it is waiting and is not.

Give the implementer a wait mechanism instead:

> Your build will outlive the command timeout, so start it in the background with a log inside
> **this worktree** and wait on the process you started. Write both files under `.forge-build/`,
> which the repository already ignores — a stray `.pid` in the working tree shows up as an
> uncommitted change and a reviewer is instructed to flag it.
>
> ```bash
> cd <worktree>
> mkdir -p .forge-build
> FORGE=Applications/Forge/.bootstrap-out/forge     # bootstrap first if absent
> nohup "$FORGE" build <profile> > .forge-build/build.log 2>&1 &
> echo $! > .forge-build/build.pid
> ```
>
> Then poll in **bounded** batches. A single unbounded `while` loop is itself subject to the same
> command timeout that forced the build into the background, and being killed mid-wait looks like a
> failure rather than an unfinished build. Cap each call well under the timeout and re-run it until
> the process is gone:
>
> ```bash
> BUILD_PID=$(cat <worktree>/.forge-build/build.pid)
> for _ in $(seq 1 16); do                                   # ~8 min, then return
>   kill -0 "$BUILD_PID" 2>/dev/null || break
>   sleep 30
> done
> kill -0 "$BUILD_PID" 2>/dev/null && echo "STILL BUILDING — run this block again" \
>   || tail -40 <worktree>/.forge-build/build.log
> ```
>
> If it prints `STILL BUILDING`, run the same block again. That is a normal cold build, not a
> failure — do not proceed to edits or verification, and do not end your turn.
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
> Waiting on a captured PID avoids all three: it cannot match a sibling, and it cannot match itself.
>
> A build that is still running is never a finished build. Confirm from the log's final lines that
> the build reported a result before you act on it.

When the harness offers a native background mode that notifies on completion, prefer it — the PID
file above is the fallback for a plain shell.

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
- **Fix only the named findings.** If you notice an unrelated problem, report it under an
  `## Also Noticed` heading rather than fixing it: the reviewers never vetted those changes, so an
  over-reaching fix pass re-opens the gate instead of closing it.
