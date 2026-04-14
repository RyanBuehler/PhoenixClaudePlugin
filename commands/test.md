---
description: Run the project's test suite using Forge. Ensures the Forge binary is present and at the expected version before testing.
---

Run the full test suite using Forge.

## 1. Ensure Forge is Ready

Follow `references/ensure-binary.md` for the **Forge** row. This guarantees `./forge` exists, is at the expected version, and is safe to invoke. If the procedure stops with a version mismatch, stop here and report it to the user.

## 2. Select Profile

Detect the active profile from existing build directories:

- If `build-editor-release` exists, use `editor-release`.
- If `build-editor-debug` exists, use `editor-debug`.
- Otherwise default to `editor-debug`.

## 3. Test with Forge

```bash
./forge test <profile> --output-on-failure
```

If the build directory for the selected profile doesn't exist, tell the user to run `/phoe:build` first.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
