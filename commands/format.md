---
name: format
description: Format staged C++ files with clang-format and verify formatting is correct.
---

Format staged files and verify:

```bash
python Tools/format.py --files=staged
python Tools/format.py --files=staged -error
```

The first command applies formatting. The second verifies it passes (matches CI behavior).

If verification fails after formatting, report the issue. If there are no staged files, inform the user.
