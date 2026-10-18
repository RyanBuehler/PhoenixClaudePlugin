---
name: build
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

- **`<target>`** — *(optional)* one of `engine`, `crucible`, `forge`, `forgegui`, `vigil`, `vigil-gui`
  (default: `engine`).

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
| `editor`         | debug      | enabled  | **default** — the build→test→verify loop       |
| `editor-release` | Release    | disabled | a **runnable windowed GUI editor**             |

Default to `editor` — it has tests enabled, so `/phoe:test` and `/phoe:verify` work against it.
The build type does not decide display capability; `editor` can map a real window.
Use `editor-release` for a release GUI run. `forge list
profiles` is the live source of truth.

## 3. Configure + Build

For an early check of one ordinary changed TU before a queued build, use the
[targeted-compilation recipe](../../references/targeted-compilation.md). Its profile provenance
and exclusive-access gates are required; the result is partial evidence, not a build.

Always run configure then build. `--json` gives a machine-readable result: stdout carries one
`{phase, progress, message}` NDJSON record per line while the build runs, then the result document
(status, durations, counts, `output_path`). Read stdout **line by line** — parsing it as a single
object, or slicing from the first brace to the last, sees the progress records as noise.

```bash
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
PROFILE=editor   # or editor-release for a GUI editor

"$FORGE" configure "$PROFILE" --json
"$FORGE" build "$PROFILE" --json
```

**On failure:** the result document carries `success:false` and a `failures` array — one
`{type, label, exit_code, diagnostics}` entry per failing node, with the compiler's output verbatim.
Read the error from there; no text-mode re-run is needed. A build that fails before any node runs
(stale cache, no graph) leaves `failures` empty and puts the reason in `message`. In text mode a
failing node's diagnostic also prints **whole**, never as an excerpt.

- **Output path:** read the built binary's path from the build result's `output_path` field — do
  not hardcode it. Shared engine artifacts land under `Applications/Forge/.forge/<tree>/bin/`, where
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

**Clean is destructive.** It deletes the build tree, which can hold files Forge did not produce,
such as Editor projects a user saved beside the binaries. Forge lists them and asks, and with no
terminal it refuses. On a refusal or a prompt, stop and show the user the listed paths. Never add
`--force` yourself: it deletes those files permanently.

---

# Tool Targets (`crucible`, `forge`, `forgegui`, `vigil`, `vigil-gui`)

The tool applications are ordinary Forge profiles — build them exactly like the engine. A plain app
name is its command-line build and a `-gui` name its windowed one (`forgegui` predates the hyphen):
`vigil` answers the verbs but opens no viewer, so build `vigil-gui` when you need the viewer. The
same holds for the `-gcc` and `-windows` variants (`vigil-gcc`/`vigil-gui-gcc`,
`vigil-windows`/`vigil-gui-windows`). Crucible is command line only.

| Target     | Profile    | Binaries produced                    |
|------------|------------|--------------------------------------|
| `crucible` | `crucible` | `crucible`, `crucible-server`        |
| `forge`    | `forge`    | `forge`                              |
| `forgegui` | `forgegui` | `forgegui`                           |
| `vigil`    | `vigil`    | `vigil` (no viewer)                  |
| `vigil-gui`| `vigil-gui`| `vigil` (with the VigilGUI viewer)   |

Building the `crucible` profile produces **both** `crucible` and `crucible-server`.

```bash
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
TARGET=crucible   # or forge, forgegui, vigil, vigil-gui

"$FORGE" configure "$TARGET" --json
"$FORGE" build     "$TARGET" --json
```

**Finding the built binary — discover, don't hardcode.** The output lands under
the configured build tree (`Applications/Forge/.forge/` for shared groups) in a subtree whose name depends on the host and build
config (build group, platform, build type), so never hardcode that subtree in a consuming command —
read `output_path` from the `build --json` result. For the Crucible CLI, use the script:

```bash
CRUCIBLE=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crucible_path.py) || exit 1
```

For `crucible`, **both**
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
- **Worktrees.** Forge finds the project root by walking up from its own executable (`argv[0]`),
  never the cwd, so it builds the checkout its binary lives in: the main checkout's `forge` run
  from a worktree silently builds main. In a worktree, bootstrap and run that worktree's own
  `forge` (a new worktree has none), or pass `--project-root=<worktree>`, which wins over
  auto-detection; `"$FORGE" --project-root=<worktree> list profiles` confirms which tree it sees.
  Each worktree owns its own `.forge/` and `.bootstrap-out/` dirs — do not symlink or reuse another
  checkout's build tree.
