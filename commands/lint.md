---
description: Run clang-tidy on changed files. Generates compilation database if needed.
---

Run clang-tidy on changed files, generating the compilation database first if missing.

## 1. Check Compilation Database

`Tools/tidy.py` needs a compile DB. **Reuse the Forge profile's** at
`build-<profile>/compile_commands.json` (e.g. `build-editor-debug/`), never bare `build/`: a bare
`Tools/tidy.py --compdb` configures a fresh `build/` with the system default compiler (GCC on
Linux) and hard-fails Phoenix's Clang-only CMake gate. Auto-detect the profile dir:

```bash
COMPDB_DIR=$(for d in build-*/; do [ -f "$d/compile_commands.json" ] && echo "${d%/}" && break; done)
```

If none exists yet, run `/phoe:build` first, or fall back to
`CC=clang CXX=clang++ python3 Tools/tidy.py --compdb` so the regen uses Clang.

## 2. Lint

```bash
python3 Tools/tidy.py ${COMPDB_DIR:+-p "$COMPDB_DIR"}
```

Test files (`*Trials.cpp`) may be skipped with `--filter '*Trials.cpp'` if the user requests.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
