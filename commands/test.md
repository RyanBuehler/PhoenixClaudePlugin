---
description: Run the project's test suite using Forge. Falls back to raw ctest if Forge is unavailable.
---

Run the full test suite, using Forge if available.

## 1. Detect Forge

Check if the Forge binary exists. Search these paths in order and use the first match:

1. `build/bin/forge`
2. `build-editor-debug/bin/forge`
3. `build-editor-release/bin/forge`

## 2. Select Profile

If Forge was found, detect the active profile from existing build directories:

- If `build-editor-release` exists, use `editor-release`
- If `build-editor-debug` exists, use `editor-debug`
- Default to `editor-debug`

## 3a. Test with Forge

If Forge is available:

```bash
<forge-binary> test <profile> --output-on-failure
```

## 3b. Fallback: Test with ctest

If no Forge binary is available, fall back to raw ctest:

```bash
ctest --test-dir build -C Release --output-on-failure
```

If the build directory doesn't exist, inform the user to run `/phoe:build` first.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
