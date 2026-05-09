---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is considered incomplete work.

The commands below are the inline equivalents of `/phoe:build`, `/phoe:format`, `/phoe:lint`,
`/phoe:test`. Run them directly to avoid nested skill invocations. Use the sub-skills when
debugging a single phase.

## 1. Build

Run `/phoe:build` — it owns version-mismatch handling and profile detection, so don't inline it.
On a fresh worktree the first call rebuilds Forge; subsequent calls are no-ops.

## 2. Format

```bash
python3 Tools/format.py --files=staged
python3 Tools/format.py --files=staged -error
```

## 3. Lint

```bash
[ -f build/compile_commands.json ] || python3 Tools/tidy.py --compdb
python3 Tools/tidy.py
```

## 4. Test

Pick the first profile with `tests_enabled: true` (`editor-debug`, then `editor-release`).
Currently `editor-release` has tests disabled, so this resolves to `editor-debug` in nearly all
cases. See `commands/test.md` if the default isn't right.

```bash
build-forge-release/bin/forge test editor-debug --output-on-failure
```

## 5. Report

Tell the user whether all checks passed or which step failed. If all passed, the work is cleared to commit.
