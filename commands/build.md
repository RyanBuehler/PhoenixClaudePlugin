---
description: Build the project using Forge profiles. Ensures the Forge binary is present and at the expected version before building.
---

Build the project using Forge.

## 1. Ensure Forge is Ready

Follow `references/ensure-binary.md` for the **Forge** row. This guarantees `./forge` exists, is at the expected version, and is safe to invoke. If the procedure stops with a version mismatch, stop here and report it to the user.

## 2. Select Profile

Detect the active profile from existing build directories:

- If `build-editor-release` exists, use `editor-release`.
- If `build-editor-debug` exists, use `editor-debug`.
- Otherwise default to `editor-debug`.

## 3. Build with Forge

```bash
./forge configure <profile>
./forge build <profile>
```

## 4. Report

Tell the user the build result — success or failure with the first error.
