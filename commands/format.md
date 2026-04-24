---
description: Format staged C++ files with clang-format and verify formatting is correct.
---

Format staged C++ files and verify the result matches CI expectations.

## 1. Format

Apply formatting to staged files:

```bash
python3 Tools/format.py --files=staged
```

## 2. Verify

Check that formatting passes (mirrors CI behavior):

```bash
python3 Tools/format.py --files=staged -error
```

If verification fails after formatting, investigate the issue. If there are no staged files, inform the user.

## 3. Report

Tell the user whether formatting passed or what issues remain.
