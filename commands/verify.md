---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is considered incomplete work.

The commands below are the inline equivalents of `/phoe:build`, `/phoe:format`, `/phoe:lint`,
`/phoe:test`. Run them directly to avoid nested skill invocations. Use the sub-skills when
debugging a single phase.

## 1. Build

Run `/phoe:build` — it owns version-mismatch handling and profile detection, so don't inline it.
On a fresh worktree the first call rebuilds Forge; subsequent calls are no-ops.

**Struct/enum layout changes need a clean build to trust.** When the change alters the in-memory
layout of a struct/enum in a header that many TUs include, an incremental module build can leave
some TUs on the old layout and produce a *phantom* trial segfault near a `vector`/copy of the
changed type (an ABI/size skew, not a logic bug). `ccache -C` does not fix it — only a clean build
(`rm -rf build-<profile>` then `/phoe:build`) is authoritative, which is what CI does anyway. Treat
such a segfault as a build artifact first, a logic bug second.

## 2. Format

Use `--files=branch` to mirror CI exactly (compares against `main`). `--files=staged` silently
passes when nothing is staged — this gate runs before `git add -A` in most workflows, so
`staged` would no-op.

```bash
python3 Tools/format.py --files=branch
python3 Tools/format.py --files=branch -error
```

`--files=branch` does **not** see untracked new files (they are not in the branch diff until
`git add`-ed), so a new file's formatting only surfaces after it is staged/committed. Stage new
files before this gate (then re-check with `--files=staged`) so violations don't slip to CI.

## 3. Lint

`Tools/tidy.py` needs a compile DB. **Reuse the Forge profile's** — it lives at
`build-<profile>/compile_commands.json` (e.g. `build-editor-debug/`), never bare `build/`. A bare
`Tools/tidy.py --compdb` configures a fresh `build/` with the system default compiler (GCC on
Linux) and hard-fails Phoenix's Clang-only CMake gate, leaving a broken `build/` behind. Point
tidy at the profile dir with `-p`:

```bash
COMPDB_DIR=$(for d in build-*/; do [ -f "$d/compile_commands.json" ] && echo "${d%/}" && break; done)
python3 Tools/tidy.py ${COMPDB_DIR:+-p "$COMPDB_DIR"}
```

If no `build-*/` has a compile DB yet, run `/phoe:build` first (Step 1), or fall back to
`CC=clang CXX=clang++ python3 Tools/tidy.py --compdb` so the regen uses Clang.

## 4. Test

Pick the first profile with `tests_enabled: true` (`editor-debug`, then `editor-release`).
Currently `editor-release` has tests disabled, so this resolves to `editor-debug` in nearly all
cases. See `commands/test.md` if the default isn't right.

```bash
build-forge-release/bin/forge test editor-debug --output-on-failure
```

## Python-only changes

If the diff is 100% Python (touches no C++, build, or test code), the phases above are no-ops:
`format.py`/`tidy.py` act only on C++, and `python3 Tools/format.py --files=staged -error` even
*errors* on zero staged C++ files (it reads as a failure when it should be a clean pass). For a
Python-only change, skip phases 1-4 and instead run the touched tool's own test suite — e.g.
`python3 -m unittest discover -s Tools/Tests`, or the relevant Python CTest target. Treat "no C++
in scope" as a clean pass, not a failure.

## 5. Report

Tell the user whether all checks passed or which step failed. If all passed, the work is cleared to commit.
