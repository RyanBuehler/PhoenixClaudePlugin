---
description: Build an executable (Forge, Crucible, Vigil) or the engine project. Single source of truth for build procedures — clean rebuilds from scratch when a binary is missing or the wrong version.
---

Build an executable from source.

## Arguments

- **`<target>`** — *(optional)* one of `forge`, `crucible`, `vigil`, or `engine` (default: `engine`).

## What This Command Owns

This is the **single source of truth** for building any executable in the Phoenix project. Other plugin commands (`/phoe:test`, `/phoe:implement`, `/phoe:plan`, `/phoe:bugfix`, `/phoe:execute`, `/phoe:verify`) should invoke `/phoe:build <target>` instead of scripting cmake or checking versions themselves. After the build step, invoke the binary via its explicit build-dir path (e.g., `build-forge-release/bin/forge`). **No symlinks, no ELF files at the repo root.**

## Tool Build Targets

| Target   | Expected Version | CMake Flag             | Build Dir              | Binaries Produced          |
|----------|------------------|------------------------|------------------------|----------------------------|
| forge    | 2026.0.0         | -DAPPLICATION=Forge    | build-forge-release    | forge                      |
| crucible | 2026.0.0         | -DAPPLICATION=Crucible | build-crucible-release | crucible, crucible-server  |
| vigil    | 2026.0.0         | -DAPPLICATION=Vigil    | build-vigil-release    | vigil                      |

This table is the source of truth. Bump a row whenever the corresponding `ApplicationsManifest.json` version changes, in lockstep with the plugin's `marketplace.json` version.

## Cross-Checkout Staleness

`CMakeCache.txt` records the absolute source path used at configure time. If a build directory was generated against one checkout and is now sitting next to a different checkout — for example, a workspace snapshot was restored to a new path, or the directory was copied between worktrees — every subsequent cmake or Forge configure invocation fails with `The current CMakeCache.txt directory ... is different than the directory ... where CMakeCache.txt was created`. Treat that condition as staleness and reset the build dir before configuring.

The check is one grep against `<build-dir>/CMakeCache.txt` and runs cheaply on every `/phoe:build` invocation:

```bash
CACHE=<build-dir>/CMakeCache.txt
if [ -f "$CACHE" ]; then
  CACHE_HOME=$(grep -m1 '^CMAKE_HOME_DIRECTORY:' "$CACHE" | cut -d= -f2)
  CURRENT_HOME=$(pwd)
  if [ "$CACHE_HOME" != "$CURRENT_HOME" ]; then
    echo "stale: $CACHE was configured from $CACHE_HOME, current is $CURRENT_HOME — removing <build-dir>"
    rm -rf <build-dir>
  fi
fi
```

Substitute the appropriate `<build-dir>` for the target being built — `build-<target>-release` for tool targets, or `build-<profile>` (e.g. `build-editor-debug`) for engine profiles. Run this check before any cmake or `forge configure` step in both procedures below.

## Procedure for Tool Targets (`forge`, `crucible`, `vigil`)

Substitute the target's values from the table for `<target>`, `<flag>`, and `<build-dir>` — where `<build-dir>` expands to `build-<target>-release`.

### 1. Version Check

```bash
build-<target>-release/bin/<target> --version
```

Treat the binary as **stale** (and rebuild) if any of the following is true:

- The binary file does not exist.
- The command exits non-zero (broken binary, missing dependency).
- The output does not match `<Target> <expected-version>` (e.g. `Forge 2026.0.0`).
- The build dir's `CMakeCache.txt` was configured from a different absolute source path — see [Cross-Checkout Staleness](#cross-checkout-staleness) for the check and the cleanup it triggers. Run that check before the version probe so a wrong-checkout cache is removed before any cmake step touches it.

If the binary is current, the build is a no-op — report "already current" and exit successfully.

For the `crucible` target, verify **both** binaries exist and report version — a partial build where only one binary lands counts as stale.

### 2. Clean Rebuild From Scratch

When stale, fully reset the build directory before configuring. We never trust an incremental build across version skews — a wrong-version binary usually means state has drifted in ways cmake won't detect:

```bash
rm -rf build-<target>-release
cmake -S . -B build-<target>-release -G Ninja <flag> -DCMAKE_BUILD_TYPE=Release
cmake --build build-<target>-release --parallel 16
```

`-G Ninja` is required — Phoenix uses C++23 modules, which CMake only supports under Ninja, Ninja Multi-Config, and recent Visual Studio generators. The default Makefiles generator fails at configure time.

### 3. Re-verify

```bash
build-<target>-release/bin/<target> --version
```

If the output still does not match the expected version, **stop and surface the mismatch to the user**. Do not fall back to an older binary or a cached artifact. This usually means the manifest version was bumped but the source wasn't regenerated, or a dependency build failed silently.

## Procedure for the `engine` Target

The engine target builds the project under test using Forge profiles. It first ensures Forge itself is current via the tool-target procedure above, then delegates the engine build to Forge.

### 1. Ensure Forge Is Current

Run the tool-target procedure for `forge` (steps 1–3 above). If Forge rebuilds, continue; if it stops with a version mismatch, stop here and report.

### 2. Select Profile

Detect the active profile from existing build directories:

- If `build-editor-release` exists, use `editor-release`.
- If `build-editor-debug` exists, use `editor-debug`.
- Otherwise default to `editor-debug`.

### 3. Cross-Checkout Cache Check

Run the [Cross-Checkout Staleness](#cross-checkout-staleness) check against `build-<profile>/` before invoking Forge. If the cache was configured from a different absolute path, this removes the build dir so the next step reconfigures cleanly instead of failing with cmake's "CMakeCache.txt directory is different" error.

### 4. Build with Forge

```bash
build-forge-release/bin/forge configure <profile>
build-forge-release/bin/forge build <profile>
```

## 5. Report

Tell the user the result: which target was built, whether it rebuilt from scratch or was already current, and the first error if the build failed.

## Notes

- **No symlinks, no root-level ELFs.** Earlier versions of this plugin created `./forge`, `./crucible` symlinks at the repo root, or left built binaries at the root. Both were fragile across worktrees and filesystems. All commands now invoke binaries via their explicit build-dir path.
- **First-time cost.** A fresh clone or fresh worktree pays one full release build per tool the first time it's needed. Subsequent invocations are instant because the version check passes.
- **Worktrees.** Each worktree owns its own build dirs. No cross-worktree sharing — that's deliberate.
- **CI.** CI uses its own build paths (`build-forge-bootstrap/`, GitHub Action wrappers). This procedure is for local dev and agent-driven sessions only.
- **Windows.** Direct build-dir invocation works the same on Windows (`build-forge-release\bin\forge.exe`). Bash command examples above assume POSIX; substitute path separators as needed.
