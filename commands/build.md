---
description: Build the project in Release configuration. Runs cmake --build with parallel jobs.
---

Build the project in Release configuration, configuring first if needed.

## 1. Configure

If the build directory doesn't exist or hasn't been configured, configure first:

```bash
cmake -S . -B build -DTESTS=ON -DCMAKE_BUILD_TYPE=Release
```

## 2. Build

```bash
cmake --build build --config Release --parallel
```

## 3. Report

Tell the user the build result — success or failure with the first error.
