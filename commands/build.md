---
description: Build the engine (via ForgePrototype) or a tool executable (Forge, Crucible, Vigil). Single source of truth for build procedures.
---

Build an executable from source.

- The **engine** is built by **ForgePrototype** — the in-process builder that replaces CMake + Ninja.
  It configures and compiles natively, and its console output is bounded by design: a full cold
  build prints ~20 progress heartbeats plus a one-line summary, instead of one streamed line per
  compile edge (a clean editor build is ~8,800 edges → ~8,800 lines on the old path).
- The **tool targets** (`forge`, `crucible`, `vigil`) are still built with CMake + Ninja. Their
  binaries are consumed by other commands via hardcoded `build-<target>-release/bin/...` paths
  (e.g. the Crucible CLI), so their output location must stay put.

## Arguments

- **`<target>`** — *(optional)* one of `engine`, `forge`, `crucible`, `vigil` (default: `engine`).

## What This Command Owns

This is the **single source of truth** for building any executable in the Phoenix project.
`/phoe:test`, `/phoe:lint`, and `/phoe:verify` build and test the engine through ForgePrototype.
`/phoe:implement`, `/phoe:bugfix`, `/phoe:plan`, `/phoe:execute` call `/phoe:build crucible` to get
the Crucible CLI. Invoke binaries via their explicit build-dir path. **No symlinks, no ELF files at
the repo root.**

---

# Engine Target (default) — ForgePrototype

## 1. The ForgePrototype Binary

Every engine build goes through the `forge-prototype` binary. Locate it, preferring the bootstrap
output that CI produces:

```bash
fp_bin() {
  for c in \
    Applications/ForgePrototype/.bootstrap-out/forge-prototype \
    build-fp-debug/bin/forge-prototype \
    build-fp-release/bin/forge-prototype; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
```

If `fp_bin` finds nothing, **bootstrap it** (cold-start compile with clang++, no CMake/Ninja):

```bash
python3 Applications/ForgePrototype/Scripts/bootstrap.py
```

This produces `Applications/ForgePrototype/.bootstrap-out/forge-prototype` and shells out only to
`git`, `python3`, and the clang toolchain. It is content-keyed: a no-op when ForgePrototype's own
sources are unchanged, a rebuild otherwise. Re-run it after pulling changes that touch
`Applications/ForgePrototype/`. Confirm the binary reports `ForgePrototype 2026.0.0`.

## 2. Pick the Profile

ForgePrototype builds by **profile**. The engine profiles are:

| Profile                       | Build Type | Tests    | Use                                            |
|-------------------------------|------------|----------|------------------------------------------------|
| `forge-builds-editor`         | Headless   | enabled  | **default** — the build→test→verify loop       |
| `forge-builds-editor-release` | Release    | disabled | a **runnable windowed GUI editor**             |

Default to `forge-builds-editor` — it has tests enabled, so `/phoe:test` and `/phoe:verify` work
against it. Use `forge-builds-editor-release` only when the user wants to *run* the editor GUI
(Headless has no window). `forge-prototype list profiles` is the live source of truth.

## 3. Configure + Build

Always run configure then build. Capture the structured result with `--json` so a successful run
stays a single machine-parseable object (status, durations, warning/error counts, built-binary path).

```bash
FP=$(fp_bin) || { python3 Applications/ForgePrototype/Scripts/bootstrap.py && FP=$(fp_bin); }
PROFILE=forge-builds-editor   # or forge-builds-editor-release for a GUI editor

"$FP" configure "$PROFILE" --json
"$FP" build "$PROFILE" --json
```

**On failure:** `--json` reports `success:false` with `error_count` but **not** the error text
(it silences the per-node stream). To see what broke, re-run the same `build` **without** `--json` —
the default tier prints a bounded head+tail excerpt of each failing node (root cause + the
`N errors generated` summary). The failed node is still dirty, so the re-run only recompiles it:

```bash
"$FP" build "$PROFILE"   # no --json: surfaces the failing compiler output
```

- **Output path:** read the built binary's path from the build result's `output_path` field — do
  not hardcode it. Engine artifacts land under
  `Applications/ForgePrototype/.forge-out/<profile>/bin/` (Headless engine work uses the
  `shared-engine-ci-linux-Headless/bin/` tree).
- **Jobs / memory:** the in-process builder keeps peak compiler output in RAM. On a memory-tight
  host, cap parallelism with `--jobs=N` (~2.5 GB/job); on a workstation the default is fine.
- **No version probe needed.** ForgePrototype tracks staleness — `configure` + `build` is always
  safe to re-run; an unchanged tree restats and exits quickly (the rescan can take a minute or two
  on a no-op, which is expected).

---

# Tool Targets (`forge`, `crucible`, `vigil`) — CMake + Ninja

These binaries are invoked by other commands via fixed `build-<target>-release/bin/` paths, so they
keep the CMake build dir. Substitute the target's values:

| Target   | Version  | CMake Flag             | Build Dir              | Binaries                  |
|----------|----------|------------------------|------------------------|---------------------------|
| forge    | 2026.0.0 | -DAPPLICATION=Forge    | build-forge-release    | forge                     |
| crucible | 2026.0.0 | -DAPPLICATION=Crucible | build-crucible-release | crucible, crucible-server |
| vigil    | 2026.0.0 | -DAPPLICATION=Vigil    | build-vigil-release    | vigil                     |

## 1. Version Check

```bash
build-<target>-release/bin/<target> --version
```

Treat as **stale** (rebuild) if: the binary is missing; the command exits non-zero; the output
doesn't match `<Target> <version>` (e.g. `Crucible 2026.0.0`); or the build dir's `CMakeCache.txt`
records a different absolute source path (cross-checkout staleness — `grep -m1 '^CMAKE_HOME_DIRECTORY:'
build-<target>-release/CMakeCache.txt`; if it differs from `pwd`, `rm -rf` the build dir first).
For `crucible`, **both** binaries must exist or it's stale. If current, report "already current".

## 2. Clean Rebuild

```bash
rm -rf build-<target>-release
cmake -S . -B build-<target>-release -G Ninja <flag> -DCMAKE_BUILD_TYPE=Release
cmake --build build-<target>-release --parallel 16
```

`-G Ninja` is required — Phoenix's C++23 modules only build under Ninja. Re-verify with `--version`;
on a persistent mismatch, **stop and surface it** (a bumped manifest version with un-regenerated
source, or a silent dependency failure) — never fall back to an older binary.

---

## Report

State the result: target/profile built, SUCCESS or FAILED with duration, the `output_path` on
success, and the first failing node's error on failure. For the engine, surface a configure-phase
failure rather than proceeding to build.

## Notes

- **Why ForgePrototype for the engine.** The old path streamed every `cmake`/`ninja` line into the
  session; a clean editor build is ~8,800 edges. ForgePrototype caps progress at ~20 heartbeats and
  `--json` reduces a successful build to one result object — the dominant `/phoe:build` token cost.
- **ccache is modules-correct here.** ForgePrototype folds each consumer's transitive imported
  interface sources into the ccache key, so a changed `.cppm` busts exactly the dependent consumers
  — safe with C++23 modules, unlike plain ccache on the CMake path.
- **Engine artifacts** live under `Applications/ForgePrototype/.forge-out/`, not `build-<profile>/`.
  clang-tidy uses `forge-prototype lint` against the same graph — see `/phoe:lint`.
- **Worktrees.** Each worktree owns its own `.forge-out/`, `.bootstrap-out/`, and `build-*/` dirs.
