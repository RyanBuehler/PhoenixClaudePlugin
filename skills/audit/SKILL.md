---
name: audit
description: Use when auditing a cold Phoenix C++ file, a set of files, or a module for drift from project conventions — style-guide violations, naming inconsistencies, comment hygiene, Phoenix-specific antipatterns, and subsystem-design smells that slip past clang-tidy and per-change review. Also handles focused single-theme sweeps via `--checks=<group>` ("audit the naming antipatterns", "sweep for reference members"). Auto-activates on phrases like "audit this file", "audit this module", "check for convention drift". Not for per-change review (use `invoke-code-reviewer`), not for UI-architecture review (use `ui-design-review`), not for include/module-import hygiene (use `invoke-lint-agent`).
---

# Audit — Phoenix Consistency Sweeper

## Purpose

Audit is a **rotational consistency sweeper** for Phoenix C++ source. It walks files that
nobody is actively editing — the ones per-change review and clang-tidy never see — and
reports drift from the project's documented conventions.

Audit is NOT a rulebook. It holds **no rules of its own**. Every rule it enforces lives in
an authoritative document that this skill reads fresh on each invocation. If a convention
isn't in one of those documents, audit does not enforce it. If you catch a recurring
violation that isn't yet documented, fix the document first — then audit will catch it next
run.

Audit is NOT a gate. `/phoe:verify` remains the commit precondition. Audit findings are
drift notes, not blockers.

## Source of truth — read fresh on every run

Before applying a single check, load the current state of these files (do **not** cache
across invocations — they change):

1. `Docs/StyleGuide.md` — formatting, naming, language features, comments, TODOs,
   design practices, error handling. **The authoritative rulebook.**
2. `CHECKS.md` (beside this file) — **audit's working catalog.** Every check with a stable
   greppable ID, a severity, a fix tier, the rulebook section that owns it, a detection
   heuristic, and a fix direction. It holds no rules of its own; it is the rulebook indexed by
   *smell*, organized the way findings are produced. Where a check and its **Rule** disagree,
   the rule wins.
3. `Docs/Patterns.md` — the idioms, and the antipatterns each supersedes. A suggested fix should
   name the pattern that replaces the shape.
4. `Docs/Lexicon.md` — the blessed word per concept and the banned ones (§Anti-terms). Consult
   before proposing any rename.
5. `CLAUDE.md` (plugin root) — Phoenix architecture: modules vs subsystems, subsystem
   interface design, object-handoff rules, subsystem-creation guidance, build/test workflow,
   color values, labels, code style supplements.
6. `references/tooling.md` — formatter/linter configuration, command conventions.
7. `references/modern-cpp.md` / `references/cpp-portability.md` — C++23 idioms, portability
   hazards. Only consult when the file under audit touches relevant territory.
8. Any `CLAUDE.md` at the engine repo root, or nested under the directory of the file being
   audited. Nested CLAUDE.md files may strengthen or refine rules for their subtree.

These documents are the SSOT. This skill is a driver.

## Invocation forms

```
/phoe:audit                          # diff mode: staged + unstaged files only
/phoe:audit <file-path>              # single file
/phoe:audit <path-1> <path-2> ...    # explicit file list
/phoe:audit <directory>              # every C++ source under the directory (recursive)
/phoe:audit <module-name>            # the module's Source/ tree (resolved via Engine/Modules/**/<name>)
/phoe:audit --rotation=N             # N oldest-mtime source files engine-wide
/phoe:audit --dry-run                # force report-only, skip the fix offer
```

Flags (combinable with any target form):

- `--fix-safe` — auto-apply mechanical fixes without prompting (see "Fix modes" below).
  Default is to prompt per-finding.
- `--scope=<public|private|both>` — restrict to `Source/Public/**`, `Source/Private/**`, or
  both. Default: both.
- `--include-tests` — include `*Trials.cpp` and files under `**/Tests/**`. Default: skip.
- `--checks=<group>` — run **only** the named `CHECKS.md` group. Accepted by letter or by name:
  `A`/`naming`, `B`/`ownership`, `C`/`errors`, `D`/`language`, `E`/`architecture`, `F`/`comments`,
  `G`/`headers`. Comma-separate to combine. A single check ID works too
  (`--checks=reference-member`). This is the focused form — a single-theme sweep whose report is
  short enough to act on in one sitting.

### Focused vs general

A **focused** run (`--checks=…`) applies only the named group or check and reports only those
findings. Everything outside the selection is out of scope — do not report it, even if you notice
it. This is what makes a themed sweep worth sending out: a report of one thing, across many files,
that a reader can work through in order.

A **general** run (every other form) applies every check in `CHECKS.md`. The catalog living in its
own file narrows nothing about a general audit; it only means the checks are addressable.

```
/phoe:audit --checks=naming --rotation=40         # one theme, forty coldest files
/phoe:audit --checks=reference-member Engine      # one check, engine-wide
/phoe:audit Engine/Modules/Ledger                 # general: every check
```

## File scope — what counts as C++ source

In-scope extensions: `.h`, `.hpp`, `.cpp`, `.cppm`, `.ixx`.

**Always skipped** unless `--include-tests`:
- `**/*Trials.cpp`, `**/Tests/**`
- Generated code: `build*/generated/**`, anything under a `build-*` directory.
- Third-party vendored code: `**/third_party/**`, `**/ThirdParty/**`, `**/external/**`.

Skip any file whose path resolves under `.forge/`, `.bootstrap-out/`, or another build output
directory — those caches contain generated `.cppm` files that are not source of truth.

## Workflow

### 1. Parse invocation and resolve targets

Resolve the invocation form into a concrete list of files:

- **No args** — `git diff --cached --name-only` + `git diff --name-only`, filter to
  in-scope extensions.
- **File path(s)** — use as-is after scope filtering.
- **Directory** — recursively enumerate in-scope files, apply always-skipped filters.
- **Module name** — locate via `Engine/{Modules,Plugins,Trials}/**/<name>/Source/` (or
  `Applications/<name>/Source/` if no module matches, or
  `Applications/*/Modules/<name>/Source/` for app-private modules); audit everything
  under `Source/`.
- **`--rotation=N`** — list in-scope files engine-wide, sort by mtime ascending, take first
  N. Rotation is the intended automation entry point.

If the resolved list is empty, report that and stop.

### 2. Load the source of truth

Read the documents in "Source of truth" above. Build an internal mental model of the
current rules. **If a document has changed since your last run in this session, the old
rules are invalid** — always re-read.

### 3. Apply checks, per file

Read `CHECKS.md` and apply every check in scope to each file, walking the file once and
collecting findings. Under `--checks=<group>`, apply only that group.

Each check carries its own severity, fix tier, and the rulebook section that owns it — take all
three from the catalog rather than re-deriving them. Cite the **Rule** in the finding, never the
check ID alone: a reader has to be able to confirm the rule without trusting the catalog.

Include-graph correctness (missing includes, forward-decl vs include choice, circular
includes, module-import hygiene) is **out of scope for audit** — delegate to
`invoke-lint-agent` when symptoms surface.

### 4. Classify severity

Each check declares its own severity in `CHECKS.md` — use it. The rubric there is the same
three-tier one `ui-design-review` uses, so a finding means the same thing whichever skill
produced it.

Deviate only when the specific site argues for it, and say so in the finding. If in doubt between
Warning and Nit, choose Warning: audit's value is catching drift, and being permissive defeats the
purpose.

### 5. Offer fixes — ask, or apply directly per mode

Audit's contract: **offer to fix, ask when unclear, leave a report of everything else.**

Every check in `CHECKS.md` names its own **fix tier** — `mechanical`, `judgment`, or `report`.
Use it; do not re-derive it per run. The three buckets below are those tiers.

Three checks carry **Requires approval** on top of their tier — `reference-member`,
`global-singleton`, and `trailing-preposition`. Under `--fix-safe` these are never touched and
never auto-asked: they go to the report with the approval requirement stated, so a rotation cannot
quietly authorize one.

Partition findings into three buckets:

- **Mechanical (safe to auto-apply).** Single-line replacements with no judgment: delete a
  decorative banner comment, rename `std::move(X)` to `Move(X)`, add a blank line after a
  `}`, convert a `TODO(foo):` to `TODO:`, add `#pragma once`, rename `Maybe*` to
  `Tentative*` or `Kind`/`*Kind` to `Type`/`*Type` (scoped to one declaration and its
  references in the same file), swap `std::forward` for `Forward`.
- **Judgment-required.** Needs a human decision: renaming an abbreviation (multiple
  readable choices), rewriting a public accessor to an intent-based operation, deciding
  whether a namespace named `Helpers` is "generic enough to be wrong," picking `Previous`
  vs a domain-specific word, deciding whether a TODO-style comment should become a Crucible
  challenge.
- **Report-only.** Architectural violations needing cross-file refactors (cross-module
  object handoff, a subsystem that should be collapsed, a singleton that needs to become a
  subsystem, a `static_cast` cluster signalling type rework, a `std::filesystem` call site
  that needs `IO::*` extended, an ad-hoc boilerplate cluster needing a shared helper
  extracted). Do not attempt these; report and say *extend the wrapper* / *extract the
  helper* when that's the right call. Swapping a hand-rolled snippet for an existing
  one-call helper is judgment-required, not mechanical — behavior equivalence needs eyes.

Behavior by flag:

- **Default** — for each mechanical finding, apply it directly. For each judgment-required
  finding, ask the user a concise question (one per turn, tightest framing possible) and
  apply their answer before moving on. Report-only findings go straight to the summary.
- **`--fix-safe`** — apply all mechanical findings without prompting. Skip
  judgment-required findings entirely (don't ask, don't apply); list them in the report.
  This mode is for automation.
- **`--dry-run`** — apply nothing, report everything.

**Never edit a test file** (`*Trials.cpp` or under `**/Tests/**`) unless the user passed
`--include-tests` **and** explicitly approved the change.

**Never edit a file with uncommitted changes unless the user has explicitly approved.**
Surface the status and ask before touching a dirty working tree.

### 6. Emit the report

```
## Audit — <target>

**Overall**: <1-3 sentences — main drift theme, main strength>
**Summary**: N Critical · M Warning · K Nit · F auto-fixed · Q asked · R report-only

### Critical (N)
- `file:line` — **title** (`check-id`)
  <explanation citing the check's Rule, e.g. `Docs/StyleGuide.md` §Comments>
  **Fix**: <action taken, prompt asked, or "report — manual refactor required">

### Warning (M)
- ...

### Nit (K)
- ...

### Auto-fixed (F)
- `file:line` — <one-line description of each mechanical change applied>

### Report-only (R)
- `file:line` — <architectural smell> — **suggested follow-up**: <Crucible-worthy action>
```

Empty sections are omitted. If a run finds nothing, emit the clean-case form:

```
## Audit — <target>

**Overall**: Clean. No drift found.
**Summary**: 0 Critical · 0 Warning · 0 Nit
```

### 7. Verify after edits

If audit applied any mechanical fixes, finish with:

1. `python3 Tools/format.py --files=branch` on the touched files (audit's mechanical fixes
   can leave formatting slightly off — let clang-format finalize). `--files=branch` mirrors
   CI; `--files=staged` would no-op here since audit edits the working tree, not the index.
2. A single-line confirmation in the report: *"Formatted N files after audit fixes."*

Do **not** run `/phoe:build`, `/phoe:verify`, or any tests after audit fixes. That's the
user's call — audit is not a gate.

## Rotation usage

Audit was designed for automated rotation. The intended pattern is:

```
/loop <interval> /phoe:audit --rotation=<N> --fix-safe
/loop <interval> /phoe:audit --rotation=<N> --checks=naming --fix-safe
```

With `--rotation=N`, audit sorts in-scope files by mtime ascending and takes the first N —
so each run bites off the coldest files first. Combined with `--fix-safe`, the rotation
auto-applies mechanical cleanups and reports judgment-required findings for the user to
review later.

For interactive one-off audits, drop the flags and run `/phoe:audit <target>`.

## What audit does NOT do

- **Per-change review** — use `invoke-code-reviewer`. Audit is for cold files.
- **Include-graph or module-import analysis** — use `invoke-lint-agent`. Audit does not
  reason about include or import correctness.
- **UI / Mosaic / Ledger architecture review** — use `ui-design-review`. Audit covers
  engine-wide conventions; UI has its own rulebook.
- **Gating commits** — use `/phoe:verify`. Audit findings are drift notes, not blockers.
- **Inventing rules** — if a rule isn't in `Docs/StyleGuide.md`, `Docs/Patterns.md`, or a
  `CLAUDE.md`, audit does not enforce it, and `CHECKS.md` may not carry a check for it. A
  recurring violation with no owning section means strengthening the repository doc first, then
  adding the check.
- **Running the build or tests** — audit is read-first, edit-light, never validates.

## Pitfalls

How this skill goes wrong.

| Pitfall | Why it fails | Do instead |
|---|---|---|
| Encoding rules inside this SKILL file or `CHECKS.md` | Drift between skill and docs — two SSOTs is zero SSOTs | Rules go in `Docs/StyleGuide.md` / `Docs/Patterns.md` / `CLAUDE.md`; a check names the section and the smell, never the rule |
| Auto-applying a **Requires approval** finding under `--fix-safe` | A rotation quietly authorizes a reference member or a singleton nobody signed off on | Report it with the approval requirement stated; never ask, never apply |
| Reporting a focused run's out-of-group findings | The point of `--checks=<group>` is a report short enough to act on | Stay in the group; note nothing else |
| Citing a check ID as the authority | The reader cannot confirm a rule they can't find | Cite the check's **Rule** — the doc section that owns it |
| Reporting findings without citing the source doc | User can't tell if audit is hallucinating a rule | Every finding cites the doc section it came from |
| Auto-fixing judgment-required findings | User loses control over naming/architecture calls | Ask, one question per turn, tightest framing |
| Editing files with uncommitted changes without asking | Conflates user's WIP with audit's fixes | Detect dirty tree, ask before touching |
| Running `/phoe:verify` at the end | Audit becomes a gate, loop takes minutes per iteration | Stop after format; validation is the user's call |
| Auditing a generated `.cppm` under `.forge/` | The file is an artifact, not source | Skip `.forge/`, `.bootstrap-out/`, `**/generated/**` |
| Using `/phoe:audit` as a commit gate | Duplicates `/phoe:verify`, slows every commit | Audit is rotational, not change-driven |

## Related skills and agents

- `invoke-code-reviewer` — per-change review with a bugs/UB/performance lens
- `invoke-lint-agent` — clang-tidy plus include/module-import dependency analysis
  (delegated to from both audit and code-reviewer when symptoms surface)
- `ui-design-review` — UI-architecture review for Tessera/Emblema/Ledger code
- `/phoe:verify` — the actual commit gate
- `/phoe:format`, `/phoe:lint` — the per-change style tools audit does **not** replace
