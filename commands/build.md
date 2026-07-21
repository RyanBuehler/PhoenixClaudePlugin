---
description: Build the engine or a tool executable (Crucible, Forge, Vigil) through Forge, the in-process builder. Single source of truth for build procedures.
---

Build an executable from source.

Everything in Phoenix — the engine **and** the tool applications (`crucible`, `forge`, `vigil`) —
builds through **Forge**, the in-process builder. There is no external build generator and no
external test runner; they were removed during the build-system cutover and a CI gate blocks their
return. Forge configures and compiles natively, and its console output is bounded by design: a full
cold build prints a handful of phase lines plus a progress heartbeat, not one streamed line per
compile edge.

## Arguments

- **`<target>`** — *(optional)* one of `engine`, `crucible`, `forge`, `vigil` (default: `engine`).

## What This Command Owns

This is the **single source of truth** for building any executable in the Phoenix project.
`/phoe:test`, `/phoe:lint`, and `/phoe:verify` build and test the engine through Forge.
`/phoe:implement`, `/phoe:bugfix`, `/phoe:plan`, `/phoe:execute` call `/phoe:build crucible` to get
the Crucible CLI. Invoke every binary via its explicit output-tree path — **no symlinks, no ELF
files at the repo root.**

## 1. The Forge Binary

Every build goes through the bootstrapped `forge` binary. Locate it, preferring the bootstrap
output that CI produces:

```bash
forge_bin() {
  [ -x Applications/Forge/.bootstrap-out/forge ] && { echo Applications/Forge/.bootstrap-out/forge; return 0; }
  return 1
}
```

If nothing is found, **bootstrap it** (cold-start compile with clang++):

```bash
python3 Applications/Forge/Scripts/bootstrap.py
```

This produces `Applications/Forge/.bootstrap-out/forge` and shells out only to `clang++`,
`clang-scan-deps`, `ar`, `git`, and Python 3.10+ (plus `wayland-scanner` + `pkg-config` for the
Linux pane closure). `ccache` is used automatically if present. It is content-keyed: a no-op when
Forge's own sources are unchanged, a rebuild otherwise. **Re-run it after pulling changes that touch
`Applications/Forge/`** — a stale bootstrap binary lags its own source and fails cold configures
with cryptic errors. From there, the bootstrapped binary rebuilds itself and the rest of Phoenix
through the regular in-process pipeline.

---

# Engine Target (default)

## 2. Pick the Profile

Forge builds by **profile**; profiles live in `Applications/Forge/Profiles/*.json` and are named
after their target. The engine profiles are:

| Profile          | Build Type | Tests    | Use                                            |
|------------------|------------|----------|------------------------------------------------|
| `editor`         | Headless   | enabled  | **default** — the build→test→verify loop       |
| `editor-release` | Release    | disabled | a **runnable windowed GUI editor**             |

Default to `editor` — it has tests enabled, so `/phoe:test` and `/phoe:verify` work against it.
("Headless" is the config name, not a no-window promise — the `editor` profile still maps a real
window.) Use `editor-release` only when the user wants to *run* the editor GUI. `forge list
profiles` is the live source of truth.

## 3. Configure + Build

Always run configure then build. Capture the structured result with `--json` so a successful run
stays a single machine-parseable object (status, durations, warning/error counts, built-binary path).

```bash
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
PROFILE=editor   # or editor-release for a GUI editor

"$FORGE" configure "$PROFILE" --json
"$FORGE" build "$PROFILE" --json
```

**On failure:** `--json` reports `success:false` with `error_count` but **not** the error text
(it silences the per-node stream). To see what broke, re-run the same `build` **without** `--json` —
the default tier prints a bounded head+tail excerpt of each failing node (root cause + the
`N errors generated` summary). The failed node is still dirty, so the re-run only recompiles it:

```bash
"$FORGE" build "$PROFILE"   # no --json: surfaces the failing compiler output
```

- **Output path:** read the built binary's path from the build result's `output_path` field — do
  not hardcode it. Engine artifacts land under `Applications/Forge/.forge-out/<tree>/bin/`, where
  `<tree>` is a per-profile name derived from the build group, platform, and build type.
- **Jobs / memory:** the in-process builder keeps peak compiler output in RAM. On a memory-tight
  host, cap parallelism with `--jobs=N` (~2.5 GB/job); on a workstation the default is fine.
- **No version probe needed.** Forge tracks staleness — `configure` + `build` is always safe to
  re-run; an unchanged tree restats and exits quickly (the rescan can take a minute or two on a
  no-op, which is expected).

**Struct/enum layout changes need a clean build to trust.** When a change alters the in-memory
layout of a struct/enum in a widely-included header, an incremental module build can leave some TUs
on the old layout and produce a *phantom* trial segfault near a `vector`/copy of the changed type
(an ABI/size skew, not a logic bug). For an authoritative clean build, `"$FORGE" clean "$PROFILE"`
first, then rebuild. Treat such a segfault as a build artifact first, a logic bug second.

---

# Tool Targets (`crucible`, `forge`, `vigil`)

The tool applications are ordinary Forge profiles — build them exactly like the engine.

| Target     | Profile    | Binaries produced                    |
|------------|------------|--------------------------------------|
| `crucible` | `crucible` | `crucible`, `crucible-server`        |
| `forge`    | `forge`    | `forge`                              |
| `vigil`    | `vigil`    | `vigil`                              |

Building the `crucible` profile produces **both** `crucible` and `crucible-server`.

```bash
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
TARGET=crucible   # or forge, or vigil

"$FORGE" configure "$TARGET" --json
"$FORGE" build     "$TARGET" --json
```

**Finding the built binary — discover, don't hardcode.** The output lands under
`Applications/Forge/.forge-out/` in a per-profile subtree whose name depends on the host and build
config (build group, platform, build type), so never hardcode that subtree in a consuming command —
read `output_path` from the `build --json` result, or discover it:

```bash
CRUCIBLE=$(find Applications/Forge/.forge-out -type f -path '*/bin/crucible' 2>/dev/null | head -1)
```

The commands that consume the Crucible CLI (`/phoe:implement`, `/phoe:bugfix`, `/phoe:plan`,
`/phoe:execute`) resolve `$CRUCIBLE` this way and call `"$CRUCIBLE"`. For `crucible`, **both**
`crucible` and `crucible-server` must exist under the output tree or the build is incomplete.

### Version check

The tool binaries report `<Target> <version> (engine <version>)`:

```bash
"$CRUCIBLE" --version
```

Treat as stale (rebuild) if the binary is missing, the command exits non-zero, or the reported
version does not match the manifest. On a persistent mismatch after a rebuild, **stop and surface
it** (a bumped manifest version with un-regenerated source, or a silent dependency failure) — never
fall back to an older binary.

---

## Report

State the result: target/profile built, SUCCESS or FAILED with duration, the `output_path` on
success, and the first failing node's error on failure. Surface a configure-phase failure rather
than proceeding to build.

## Notes

- **ccache is modules-correct here.** Forge folds each consumer's transitive imported interface
  sources into the ccache key, so a changed `.cppm` busts exactly the dependent consumers — safe
  with C++23 modules.
- **clang-tidy** runs through `forge lint` against the same build graph — see `/phoe:lint`.
- **Worktrees.** Forge resolves the project root from the executable's location, not the cwd, so a
  bootstrapped binary run from a worktree still builds the worktree it lives in. Each worktree owns
  its own `.forge-out/`, `.forge/`, and `.bootstrap-out/` dirs.
