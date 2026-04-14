# Ensure Binary Procedure

Before invoking `./forge`, `./crucible`, or `./vigil`, verify the repo-root symlink exists and the embedded version matches the expected version below. If either check fails, rebuild and re-symlink, then verify again. Never proceed with a missing or wrong-version binary.

## Expected Versions

| App      | Expected Version | CMake Flag             | Build Dir              | Symlinks                        |
|----------|------------------|------------------------|------------------------|---------------------------------|
| Forge    | 2026.0.0         | -DAPPLICATION=Forge    | build-forge-release    | ./forge                         |
| Crucible | 2026.0.0         | -DAPPLICATION=Crucible | build-crucible-release | ./crucible, ./crucible-server   |
| Vigil    | 2026.0.0         | -DAPPLICATION=Vigil    | build-vigil-release    | ./vigil                         |

Crucible is a client/server split: one CMake build produces both the `crucible` CLI and the `crucible-server` daemon. Both need symlinks at repo root — check both when verifying, and symlink both when rebuilding.

This table is the source of truth. Bump a row whenever the corresponding `ApplicationsManifest.json` version changes; that bump belongs in the same change that bumps the plugin's `marketplace.json` version.

## Procedure (per app)

Run these steps at the project root. Substitute the app-specific values from the table above for `<app>`, `<flag>`, and `<build-dir>`.

### 1. Check

```bash
./<app> --version
```

Rebuild if any of the following is true:

- The symlink `./<app>` does not exist.
- The command exits non-zero (dangling symlink, broken binary, missing dependencies).
- The output does not match `<App> <expected-version>` (e.g. `Forge 2026.0.0`).

Otherwise the binary is current — skip to step 4.

### 2. Rebuild

```bash
cmake -S . -B <build-dir> -G Ninja <flag> -DCMAKE_BUILD_TYPE=Release
cmake --build <build-dir> --parallel
ln -sfn <build-dir>/bin/<app> ./<app>
```

`-G Ninja` is required — Phoenix uses C++23 modules, which CMake only supports under the Ninja, Ninja Multi-Config, and recent Visual Studio generators. The default Makefiles generator fails at configure time.

For Crucible, repeat the symlink step for both binaries:

```bash
ln -sfn build-crucible-release/bin/crucible ./crucible
ln -sfn build-crucible-release/bin/crucible-server ./crucible-server
```

The `ln -sfn` form atomically replaces any existing symlink and avoids the `ln -sf` dereferencing footgun.

### 3. Re-verify

```bash
./<app> --version
```

If the output still does not match the expected version, stop and report the mismatch to the user. Do not fall back to an older binary. This usually means the manifest version was bumped but the source wasn't regenerated, or a dependency build failed silently.

### 4. Proceed

The binary is ready. Invoke it via the repo-root symlink (`./forge`, `./crucible`, `./vigil`) — never via the build-dir path, so stale copies in other build dirs can't shadow the canonical one.

## Notes

- **First-time cost:** a fresh clone or fresh worktree pays one full release build per app when the first command needing it runs. Subsequent invocations are instant because `./<app> --version` already matches.
- **Worktrees:** each worktree has its own symlink and its own build dir. No cross-worktree sharing; that's deliberate.
- **CI:** CI uses its own build paths (`build-forge-bootstrap/`, GitHub Action wrappers). This procedure is for local dev and agent-driven sessions only.
- **Windows:** `ln -sfn` is POSIX. On Windows, use either developer-mode symlinks or a `.cmd` shim pointing at the build-dir binary. Not scripted yet.
