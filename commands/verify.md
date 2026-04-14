---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via Forge. The mandatory pre-push check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

`/phoe:build` and `/phoe:test` will ensure `./forge` is present and current before running (see `references/ensure-binary.md`). On a fresh worktree, the first step will rebuild Forge; subsequent runs are instant.

## 1. Build

Run `/phoe:build` — ensures Forge is ready, then configures and builds the project.

## 2. Format

Run `/phoe:format` — format staged files and verify.

## 3. Lint

Run `/phoe:lint` — run clang-tidy on changed files.

## 4. Test

Run `/phoe:test` — run the test suite via Forge.

## 5. Write Verification Marker

If all four steps pass, write the marker so the pre-push hook allows the push:

```bash
mkdir -p ~/.claude/tmp && date +%s > ~/.claude/tmp/verification-passed
```

This file is consumed (deleted) by the pre-push hook after a successful push.

## 6. Report

Tell the user whether all checks passed or which step failed.
