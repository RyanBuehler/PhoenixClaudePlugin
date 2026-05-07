---
name: audit
description: Use when auditing a cold Phoenix C++ file, a set of files, or a module for drift from project conventions — style-guide violations, naming inconsistencies, comment hygiene, Phoenix-specific antipatterns, and subsystem-design smells that slip past clang-tidy and per-change review. Auto-activates on phrases like "audit this file", "audit this module", "sweep for style drift", "check for convention drift", "consistency pass"; also invocable directly via `/phoe:audit`. Not for per-change review (use `invoke-code-reviewer`), not for UI-architecture review (use `ui-design-review`), not for include/module-import hygiene (use `invoke-lint-agent`), and not a gate — `/phoe:verify` remains the commit precondition.
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

1. `references/style-guide.md` — formatting, naming, language features, comments, TODOs,
   design practices, error handling. **The authoritative rulebook.**
2. `CLAUDE.md` (plugin root) — Phoenix architecture: modules vs subsystems, subsystem
   interface design, object-handoff rules, subsystem-creation guidance, build/test workflow,
   color values, labels, code style supplements.
3. `references/tooling.md` — formatter/linter configuration, command conventions.
4. `references/modern-cpp.md` / `references/cpp-portability.md` — C++23 idioms, portability
   hazards. Only consult when the file under audit touches relevant territory.
5. Any `CLAUDE.md` at the engine repo root, or nested under the directory of the file being
   audited. Nested CLAUDE.md files may strengthen or refine rules for their subtree.

These documents are the SSOT. This skill is a driver.

## Invocation forms

```
/phoe:audit                          # diff mode: staged + unstaged files only
/phoe:audit <file-path>              # single file
/phoe:audit <path-1> <path-2> ...    # explicit file list
/phoe:audit <directory>              # every C++ source under the directory (recursive)
/phoe:audit <module-name>            # the module's Source/ tree (resolved via Modules/**/<name>)
/phoe:audit --rotation=N             # N oldest-mtime source files engine-wide
/phoe:audit --dry-run                # force report-only, skip the fix offer
```

Flags (combinable with any target form):

- `--fix-safe` — auto-apply mechanical fixes without prompting (see "Fix modes" below).
  Default is to prompt per-finding.
- `--scope=<public|private|both>` — restrict to `Source/Public/**`, `Source/Private/**`, or
  both. Default: both.
- `--include-tests` — include `*Trials.cpp` and files under `**/Tests/**`. Default: skip.

## File scope — what counts as C++ source

In-scope extensions: `.h`, `.hpp`, `.cpp`, `.cppm`, `.ixx`.

**Always skipped** unless `--include-tests`:
- `**/*Trials.cpp`, `**/Tests/**`
- Generated code: `build*/generated/**`, anything under a `build-*` directory.
- Third-party vendored code: `**/third_party/**`, `**/ThirdParty/**`, `**/external/**`.

Skip any file whose path resolves under `build-*`, `cmake-build-*`, or another CMake output
directory — those caches contain generated `.cppm` files that are not source of truth.

## Workflow

### 1. Parse invocation and resolve targets

Resolve the invocation form into a concrete list of files:

- **No args** — `git diff --cached --name-only` + `git diff --name-only`, filter to
  in-scope extensions.
- **File path(s)** — use as-is after scope filtering.
- **Directory** — recursively enumerate in-scope files, apply always-skipped filters.
- **Module name** — locate via `Modules/**/<name>/Source/` (or `Applications/<name>/Source/`
  if no module matches); audit everything under `Source/`.
- **`--rotation=N`** — list in-scope files engine-wide, sort by mtime ascending, take first
  N. Rotation is the intended automation entry point.

If the resolved list is empty, report that and stop.

### 2. Load the source of truth

Read the documents in "Source of truth" above. Build an internal mental model of the
current rules. **If a document has changed since your last run in this session, the old
rules are invalid** — always re-read.

### 3. Apply checks, per file

For each file, walk it once and collect findings. Findings cluster into the following
categories. **The specific rules come from the docs** — this is only the category list so
you know where to look.

- **Style-guide compliance** (`references/style-guide.md`)
  - Formatting rules clang-format does not enforce (blank line after `}`, `if`-init
    refactor opportunity).
  - Naming: member/global/static/local prefix patterns, atomic-bool prefix, abbreviations,
    `Old*`→`Previous*`, `Maybe*`→`Tentative*`, single-letter non-loop names, overlong
    acronyms vs spelled-out names.
  - Language features: forbidden keywords (`try`, `catch`, `throw`, `noexcept`,
    `dynamic_cast`, `typeid`, `reinterpret_cast`, `[[deprecated]]`), `auto` on
    error-bearing returns, trailing return types, `const` correctness.
  - **`Move`/`Forward` vs `std::move`/`std::forward`** — grep should return zero hits on
    the `std::` forms in shared source.
  - Comments: decorative banners, temporal narration, stale references (file paths, line
    numbers, commit hashes, PR #, Crucible labels), stacked `//` paragraphs, what-comments
    over self-documenting code, public-API header declarations without a purpose comment,
    `TODO(…):` parenthesized prefixes.
  - Error handling: silent discards of error-bearing returns (`(void)`, `std::ignore`,
    `[[maybe_unused]] auto _ =`), default-constructed `T` returned from an
    `expected<T, E>` function.
  - Design practices: `new`/`delete`, singletons (private ctor + static Get/Instance),
    macros without exemption, `#ifdef`/`#if` in shared code, `// NOLINT` /
    `// clang-format off` without an adjacent justification comment, raw strings as
    identity keys where `Label` is required.
  - Namespaces: anonymous, `Detail`-named, empty/generic.
  - `std::memory_order` without a nearby explaining comment.

- **Phoenix architecture** (`CLAUDE.md`)
  - Cross-module object handoff (`FooModule&`/`FooModule*`/`shared_ptr<FooModule>` as a
    parameter outside `FooModule`'s own files).
  - Subsystem interfaces with `GetX()` lazy accessors, new types declared inside a
    subsystem header, subsystem methods that don't correspond to a method on the underlying
    module.
  - Public accessors returning references to owned internals.
  - Color literals in 0–255 or hex form not normalized to 0–1.
  - Preprocessor guards outside platform/Vulkan modules.

- **Header hygiene**
  - `.h` / `.hpp` without `#pragma once`.
  - Traditional `#ifndef`/`#define`/`#endif` guards.
  - Include groups misordered or unsorted within their group (case-insensitive).

Include-graph correctness (missing includes, forward-decl vs include choice, circular
includes, module-import hygiene) is **out of scope for audit** — delegate to
`invoke-lint-agent` when symptoms surface.

### 4. Classify severity

Use the same three-tier rubric `ui-design-review` uses:

- **Critical** — runtime/correctness risk (use-after-free shape, swallowed error,
  architecture contract violation with code reaching across a module boundary, forbidden
  keyword that silently changes semantics).
- **Warning** — tech-debt, convention violation without runtime risk, maintainability smell
  (most naming/comment/formatting findings, `std::move` vs `Move`).
- **Nit** — style consistency, documentation polish.

If in doubt between Warning and Nit, choose Warning. Audit's value is catching drift; being
permissive defeats the purpose.

### 5. Offer fixes — ask, or apply directly per mode

Audit's contract: **offer to fix, ask when unclear, leave a report of everything else.**

Partition findings into three buckets:

- **Mechanical (safe to auto-apply).** Single-line replacements with no judgment: delete a
  decorative banner comment, rename `std::move(X)` to `Move(X)`, add a blank line after a
  `}`, convert a `TODO(foo):` to `TODO:`, add `#pragma once`, rename `Maybe*` to
  `Tentative*` (scoped to one declaration and its references in the same file), swap
  `std::forward` for `Forward`.
- **Judgment-required.** Needs a human decision: renaming an abbreviation (multiple
  readable choices), rewriting a public accessor to an intent-based operation, deciding
  whether a namespace named `Helpers` is "generic enough to be wrong," picking `Previous`
  vs a domain-specific word, deciding whether a TODO-style comment should become a Crucible
  challenge.
- **Report-only.** Architectural violations that require cross-file refactors (cross-module
  object handoff, a subsystem that should be collapsed, a singleton that needs to become a
  subsystem). Do not attempt these; surface them in the report for human follow-up.

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
- `file:line` — **title**
  <explanation citing the rule and the doc it comes from, e.g. style-guide.md §Comments>
  **Fix**: <action taken, prompt asked, or "report-only — manual refactor required">

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

1. `python3 Tools/format.py --files=staged` on the touched files (audit's mechanical fixes
   can leave formatting slightly off — let clang-format finalize).
2. A single-line confirmation in the report: *"Formatted N files after audit fixes."*

Do **not** run `/phoe:build`, `/phoe:verify`, or any tests after audit fixes. That's the
user's call — audit is not a gate.

## Rotation usage

Audit was designed for automated rotation. The intended pattern is:

```
/loop <interval> /phoe:audit --rotation=<N> --fix-safe
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
- **Inventing rules** — if a rule isn't in `style-guide.md` or `CLAUDE.md`, audit does not
  enforce it. Strengthen the docs first.
- **Running the build or tests** — audit is read-first, edit-light, never validates.

## Anti-patterns

| Anti-pattern | Why it fails | Do instead |
|---|---|---|
| Encoding rules inside this SKILL file | Drift between skill and docs — two SSOTs is zero SSOTs | Rules go in `style-guide.md` / `CLAUDE.md`; audit reads them |
| Reporting findings without citing the source doc | User can't tell if audit is hallucinating a rule | Every finding cites the doc section it came from |
| Auto-fixing judgment-required findings | User loses control over naming/architecture calls | Ask, one question per turn, tightest framing |
| Editing files with uncommitted changes without asking | Conflates user's WIP with audit's fixes | Detect dirty tree, ask before touching |
| Running `/phoe:verify` at the end | Audit becomes a gate, loop takes minutes per iteration | Stop after format; validation is the user's call |
| Auditing a generated `.cppm` under `build-*/` | The file is an artifact, not source | Skip `build-*`, `cmake-build-*`, `**/generated/**` |
| Using `/phoe:audit` as a commit gate | Duplicates `/phoe:verify`, slows every commit | Audit is rotational, not change-driven |

## Related skills and agents

- `invoke-code-reviewer` — per-change review with a bugs/UB/performance lens
- `invoke-lint-agent` — clang-tidy plus include/module-import dependency analysis
  (delegated to from both audit and code-reviewer when symptoms surface)
- `ui-design-review` — UI-architecture review for Tessera/Emblema/Ledger code
- `/phoe:verify` — the actual commit gate
- `/phoe:format`, `/phoe:lint` — the per-change style tools audit does **not** replace
