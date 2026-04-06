---
name: ui-design-review
description: Reviews UI code against Phoenix Mosaic architecture rules, conventions, and design patterns. Catches runtime risks, convention violations, and unidirectional-flow breaches in Tessera/Emblema/Ledger code.
---

Review UI code in the Phoenix engine for architecture violations, convention
issues, and runtime risks. This is a read-only analysis skill — it identifies
findings and produces an actionable fix task list but never edits files.

## Trigger phrases

Activate when the user says any of:
- "review UI code", "check Mosaic widget", "review Tessera", "review Emblema"
- "UI code review", "design review this panel", "audit Mosaic code"
- "review UI architecture"
- Explicit invocation via `/ui-design-review`

## Invocation forms

```
/ui-design-review                              # default: staged + unstaged diff
/ui-design-review <file-path>                  # target mode: one file
/ui-design-review <directory-path>             # target mode: every GUI file in dir
/ui-design-review <class-or-symbol-name>       # target mode: grep, find def, review
/ui-design-review --embed [...args]            # delegation mode: findings only
```

## Workflow

### 1. Parse invocation

- **No arg** — diff mode. Run `git diff --cached --name-only` + `git diff --name-only`
  to get staged + unstaged files, then filter to UI-relevant files.
- **File path** — target that single file.
- **Directory** — target every GUI file in that directory.
- **Class/symbol name** — use Grep to locate the definition file, then target it.
- **`--embed` flag** — suppress header/summary, emit findings sections only (for
  splicing into other review skills' output).

### 2. Identify UI-relevant files

A file is in scope if ANY of these match:
1. **Path** matches `Modules/Rendering/Mosaic/**`, `Modules/Rendering/Montage/**`,
   `Applications/Editor/**`, `Applications/*/Source/**/UI*`, or `Modules/Ledger/**`
2. **Includes** reference `Tessera.h`, `Canvas.h`, `Panel.h`, `Emblema.h`,
   `Ledger.h`, `IEntry.h`, `IAccountState.h`, or anything from `Mosaic/`/`Montage/`
3. **Type definitions** inherit from `Tessera`/`Canvas`/`Panel`/`Emblema`/`ITessera`,
   or implement `IAccountState`/`IEntry`

**Skip**: `**/Tests/**`, `**/*.test.*`, `**/*Trials*` (unless `--include-tests`).

### 3. Ground against current codebase

Before applying checks, read these files fresh (do not cache across invocations):
- `Modules/Rendering/Mosaic/Source/Public/Tessera.h` — widget base class contract
- `Modules/Rendering/Mosaic/Source/Public/Style/Theme.h` — current Theme fields
- `Modules/Ledger/Source/Public/Ledger.h` — Ledger API
- `Modules/Ledger/Source/Public/IEntry.h` — Entry interface
- `Modules/Ledger/Source/Public/EntryCategory.h` — category definitions
- `Modules/Ledger/Source/Public/IAccountState.h` — Account state interface
- Any `CLAUDE.md` at repo root, under `Modules/Rendering/Mosaic/`, or `Applications/Editor/`
- `~/.claude/projects/-home-ryan-Agents-Agent3/memory/MEMORY.md` — active conventions

### 4. Apply checks

Read CHECKS.md and apply every check to each in-scope file. Also read
PHOENIX_RULES.md for vocabulary and architecture context. Collect findings.

### 5. Classify findings

Assign severity per the rubric in CHECKS.md:
- **Critical** — runtime failure risk (crash, deadlock, leak, state corruption)
  OR non-negotiable Phoenix rule violation
- **Warning** — tech debt, maintainability smell, convention violation without
  runtime risk, performance hazard, UX defect
- **Nit** — style, consistency, documentation

### 6. Emit output

**Standalone** (default):
```
## UI Design Review — <target>

**Overall**: <1-3 sentences — direction, main concern, main strength>
**Summary**: N Critical · M Warning · K Nit

### Critical (N)
- `file:line` — **title** (`check-name`)
  <explanation using Phoenix vocabulary>
  **Fix**: <concrete action>

### Warning (M)
- ...

### Nit (K)
- ...

### Suggested fix tasks
1. [Critical] file:line — action
2. [Warning] file:line — action
```

Empty severity sections are omitted entirely.

**Clean-case** (no findings):
```
## UI Design Review — <target>

**Overall**: Clean. No violations found.
**Summary**: 0 Critical · 0 Warning · 0 Nit
```

**Embed mode** (`--embed`):
- Suppress `## UI Design Review` header and `**Overall**`/`**Summary**`
- Preserve severity sections + fix tasks
- Clean case: single-line `### UI design review — no findings`

### 7. Never edit files

The fix task list exists so the user (or a follow-up skill) can act on
findings. This skill is read-only.
