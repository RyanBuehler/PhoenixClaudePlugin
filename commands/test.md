---
name: test
description: Run the project's test suite via CTest. Shows output on failure.
---

Run all tests:

```bash
ctest --test-dir build -C Release --output-on-failure
```

If tests fail, report which tests failed and show their output. If the build directory doesn't exist, inform the user to run `/build` first.
