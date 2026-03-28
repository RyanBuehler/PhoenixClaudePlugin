---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

`/phoe:build` and `/phoe:test` will use Forge automatically when available, falling back to raw cmake/ctest otherwise.

## 1. Build

Run `/phoe:build` — configure and build the project (via Forge or cmake fallback).

## 2. Format

Run `/phoe:format` — format staged files and verify.

## 3. Lint

Run `/phoe:lint` — run clang-tidy on changed files.

## 4. Test

Run `/phoe:test` — run the test suite (via Forge or ctest fallback).

## 5. Write Verification Marker

If all four steps pass, write the marker so the pre-commit hook allows the commit:

```bash
mkdir -p ~/.claude/tmp && date +%s > ~/.claude/tmp/verification-passed
```

This file is consumed (deleted) by the pre-commit hook after a successful commit.

## 6. Report

Tell the user whether all checks passed or which step failed.
