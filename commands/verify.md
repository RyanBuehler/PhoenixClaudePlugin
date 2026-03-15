---
description: Full CI-mirror verification sequence — configure, build, format check, and test. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence by executing these commands in order. Stop on the first failure:

1. `/build` — configure and build the project
2. `/format` — format staged files and verify
3. `/lint` — run clang-tidy on changed files
4. `/test` — run the test suite

All four must pass before changes should be committed. This mirrors the CI pipeline.

If all four pass, write the verification marker so the pre-commit hook allows the commit:

```bash
mkdir -p ~/.claude/tmp && date +%s > ~/.claude/tmp/verification-passed
```

This file is consumed (deleted) by the pre-commit hook after a successful commit.
