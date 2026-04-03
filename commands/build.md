---
description: Build the project using Forge profiles. Falls back to raw cmake if Forge is unavailable.
---

Build the project, using Forge if available.

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

## 3a. Build with Forge

If Forge is available, configure and build:

```bash
<forge-binary> configure <profile>
<forge-binary> build <profile>
```

## 3b. Fallback: Build with cmake

If no Forge binary is available, fall back to raw cmake:

```bash
cmake -S . -B build -DTESTS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --parallel
```

## 4. Report

Tell the user the build result — success or failure with the first error.
