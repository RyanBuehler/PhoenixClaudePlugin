---
description: Format C++ files on the current branch with clang-format and verify formatting is correct.
---

Format branch-modified C++ files and verify the result matches CI expectations.

`--files=branch` (diff against `main`) is the same scope CI uses. `--files=staged` would
silently succeed when nothing is staged — avoid it.

## 1. Format

Apply formatting to branch-modified files:

```bash
python3 Tools/format.py --files=branch
```

## 2. Verify

Check that formatting passes (mirrors CI behavior):

```bash
python3 Tools/format.py --files=branch -error
```

If verification fails after formatting, investigate the issue. If there are no branch-modified files, inform the user.

## 3. Report

Tell the user whether formatting passed or what issues remain.
