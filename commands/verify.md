---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

`/phoe:build` is the single source of truth for building executables — it ensures Forge is present and at the expected version. It rebuilds from scratch when either of those fails. On a fresh worktree, the first step will rebuild Forge; subsequent runs are instant.

Run this **before committing**. A commit made without passing verification is considered incomplete work.

## 1. Build

Run `/phoe:build` — ensures Forge is ready, then configures and builds the project.

## 2. Format

Run `/phoe:format` — format staged files and verify.

## 3. Lint

Run `/phoe:lint` — run clang-tidy on changed files.

## 4. Test

Run `/phoe:test` — run the test suite via Forge.

## 5. Report

Tell the user whether all checks passed or which step failed. If all passed, the work is cleared to commit.
