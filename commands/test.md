---
description: Run the project's test suite via CTest. Shows output on failure.
---

Run the full test suite via CTest in Release configuration.

## 1. Run Tests

```bash
ctest --test-dir build -C Release --output-on-failure
```

If the build directory doesn't exist, inform the user to run `/phoe:build` first.

## 2. Report

Tell the user which tests passed. If any failed, show their names and output.
