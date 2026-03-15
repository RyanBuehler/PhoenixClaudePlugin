---
description: Build the project in Release configuration. Runs cmake --build with parallel jobs.
---

Build the project:

```bash
cmake --build build --config Release --parallel
```

If the build directory doesn't exist or hasn't been configured, configure first:

```bash
cmake -S . -B build -DTESTS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --parallel
```

Report the build result — success or failure with the first error.
