---
name: audit
description: Use when auditing cold Phoenix source — a file, a set of files, or a module — for drift from project conventions. Dispatches one named audit type per run: logging, comments, header, style, architecture, profiling, or optimization. Auto-activates on phrases like "audit this file", "audit the logging in X", "check for convention drift", "audit this module's comments". Not for per-change review (use `invoke-code-reviewer`), not for UI-architecture review (use `ui-design-review`), not for include-graph or module-import hygiene (use `invoke-lint-agent`).
---

# Audit — Phoenix Consistency Sweeper

## What this file is

A **dispatcher**. It resolves targets, sets severity, and shapes the report. It holds no
rules and describes no specific audit.

Three layers, and each one only knows about the next:

```
SKILL.md            dispatch, targets, severity, report shape   (this file)
  audits/<type>.md  how to conduct that one audit               (workflow)
    references/*.md the rules themselves                        (SSOT)
```

A run loads **this file, one workflow doc, and the SSOT docs that workflow doc names.**
Nothing else. That is the point of the split — an audit of log messages should never pay
for the architecture rulebook.

Audit is not a gate. `/phoe:verify` remains the commit precondition; findings are drift
notes, not blockers.

## Audit types

| Type | Sweeps for | Workflow | SSOT |
|---|---|---|---|
| `logging` | Log level, message content, form, machine readability | `audits/logging.md` | `references/logging.md` |
| `comments` | In-source comments and TODOs | `audits/comments.md` | `references/comments.md` |
| `header` | The top of a file — copyright notice, description, guard, import preamble | `audits/header.md` | `references/header.md` |
| `style` | Naming, language features, error handling, design practices | `audits/style.md` | `references/style-guide.md` |
| `architecture` | Module/subsystem boundaries, ownership tiers, object handoff | `audits/architecture.md` | `CLAUDE.md` |
| `profiling` | Whether a system's cost is visible and correctly attributed | `audits/profiling.md` | `references/profiling.md` |
| `optimization` | Waste — allocation, copies, redundant work, layout | `audits/optimization.md` | `references/optimization.md` |

## Invocation

```
/phoe:audit <type> <target> [flags]
```

With no type, list the table above and ask which one — do not guess, and do not run all
of them.

Target forms (`<target>` defaults to diff mode when omitted):

```
/phoe:audit logging                       # staged + unstaged files
/phoe:audit logging <file>                # one file
/phoe:audit logging <file> <file> ...     # explicit list
/phoe:audit logging <directory>           # recursive
/phoe:audit logging <module-name>         # the module's Source/ tree
/phoe:audit logging --rotation=N          # N coldest files engine-wide
```

Flags, combinable with any target:

- `--fix-safe` — apply mechanical fixes without prompting, skip judgment-required ones.
  The automation mode.
- `--dry-run` — apply nothing, report everything.
- `--scope=<public|private|both>` — restrict to `Source/Public/**`, `Source/Private/**`,
  or both. Default: both.
- `--include-tests` — include `*Trials.cpp` and `**/Tests/**`. Default: skip.

## Resolving targets

- **No target** — `git diff --cached --name-only` plus `git diff --name-only`.
- **Module name** — `Engine/{Modules,Plugins,Trials}/**/<name>/Source/`, else
  `Applications/<name>/Source/`, else `Applications/*/Modules/<name>/Source/`.
- **`--rotation=N`** — sort in-scope files by mtime ascending, take the first N. Coldest
  first; this is the automation entry point.

In-scope extensions: `.h`, `.hpp`, `.cpp`, `.cppm`, `.ixx`, `.inl`. A workflow doc may
narrow this further.

Always skipped: `**/*Trials.cpp` and `**/Tests/**` without `--include-tests`; generated
code under `build*/`, `cmake-build-*/`, `**/generated/**`; vendored code under
`**/ThirdParty/**`, `**/third_party/**`, `**/external/**`.

If the resolved list is empty, say so and stop.

## Load the rules fresh

Read the workflow doc and its SSOT documents **on every invocation**. Never work from a
cached memory of them — they change, and a stale rule reported as current is worse than
no audit. Also read any `CLAUDE.md` at the engine repo root or nested under the target's
directory; a nested one may strengthen rules for its subtree.

**Audit invents no rules.** If a finding cannot cite a rule ID or a document section, it
is not a finding. When you notice recurring drift no document covers, say so in the
report — the fix is to strengthen the document, and the next run will catch it.

## Severity

- **Critical** — runtime or correctness risk: a swallowed error, an architecture contract
  broken across a module boundary, a leak of secrets, a flood or cost in a shipping build.
- **Warning** — convention violation without runtime risk; maintainability debt.
- **Nit** — style consistency, polish.

Each workflow doc maps its own rules onto these three. When torn between Warning and Nit,
choose Warning — being permissive defeats the purpose.

## Fixing

Partition every finding into one of three buckets; each workflow doc says which of its
rules fall where.

- **Mechanical** — a single-site replacement with no judgment involved.
- **Judgment-required** — more than one defensible answer. Ask one concise question per
  turn, tightest framing possible, and apply the answer before moving on.
- **Report-only** — needs a cross-file refactor. Do not attempt it; name the follow-up.

Behavior by flag: **default** applies mechanical fixes and asks about judgment ones;
**`--fix-safe`** applies mechanical only and lists the rest; **`--dry-run`** applies
nothing.

**Never edit a test file** unless `--include-tests` was passed *and* the user approved the
change. **Never edit a file with uncommitted changes** without surfacing that and asking
first.

## Report

```
## Audit (<type>) — <target>

**Overall**: <1-3 sentences: the main drift theme, and the main strength>
**Summary**: N Critical · M Warning · K Nit · F auto-fixed · Q asked · R report-only

### Critical (N)
- `file:line` — **title** [`L14`]
  <what is wrong, in terms of the cited rule>
  **Fix**: <applied | asked | report-only: manual refactor required>

### Warning (M)
### Nit (K)
### Auto-fixed (F)
- `file:line` — <the change applied>
### Report-only (R)
- `file:line` — <the smell> — **follow-up**: <the Crucible-worthy action>
```

Every finding cites its rule ID in brackets. Omit empty sections. A clean run:

```
## Audit (<type>) — <target>

**Overall**: Clean. No drift found.
**Summary**: 0 Critical · 0 Warning · 0 Nit
```

## After edits

If any fix was applied, run `python3 Tools/format.py --files=branch` and note
*"Formatted N files after audit fixes."* in the report. `--files=branch` mirrors CI;
`--files=staged` would no-op, since audit edits the working tree rather than the index.

Do **not** run `/phoe:build`, `/phoe:verify`, or tests. That is the user's call.

## Rotation

Audit was built for it:

```
/loop <interval> /phoe:audit <type> --rotation=<N> --fix-safe
```

Coldest files first, mechanical cleanups applied, judgment findings left in the report.

## What audit does not do

| Not this | Use instead |
|---|---|
| Per-change review | `invoke-code-reviewer` |
| Include-graph / module-import analysis | `invoke-lint-agent` |
| UI / Mosaic / Ledger architecture | `ui-design-review` |
| Gating a commit | `/phoe:verify` |
| Running the build or tests | nothing — audit never validates |
| Inventing a rule | strengthen the SSOT doc first |

## Anti-patterns

| Anti-pattern | Why it fails | Do instead |
|---|---|---|
| Putting rules in this file or a workflow doc | Two SSOTs is zero SSOTs | Rules go in `references/`; audit reads them |
| Loading every workflow doc "to be thorough" | Burns the context the split exists to save | One type per run |
| A finding with no rule ID | The user cannot tell audit from hallucination | Cite the ID, or drop the finding |
| Auto-fixing a judgment call | The user loses control of their own naming | Ask, one question per turn |
| Editing a dirty working tree unasked | Conflates the user's WIP with audit's fixes | Surface it, then ask |
| Running `/phoe:verify` at the end | Audit becomes a gate; the loop takes minutes | Stop after format |
| Auditing a generated `.cppm` | It is an artifact, not source | Skip `build-*`, `**/generated/**` |
