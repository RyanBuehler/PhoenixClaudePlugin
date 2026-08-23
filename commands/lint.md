---
description: Run clang-tidy on changed files through Forge.
---

Run clang-tidy on branch-changed C++ files through Forge's `lint` command. It resolves the
compilation context from the in-process build graph itself, so there's no separate compile-database
step — the graph already knows every TU's exact flags and module imports.

## 1. Locate the Builder

```bash
forge_bin() {
  [ -x Applications/Forge/.bootstrap-out/forge ] && { echo Applications/Forge/.bootstrap-out/forge; return 0; }
  return 1
}
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
```

## 2. Lint

```bash
"$FORGE" lint
```

This lints the **branch** surface — every C++ file differing from `main`, staged or not. That is
the default (`--files=branch`); `--all` lints the whole repo and `--staged` narrows to the index.

**An empty run is not a pass.** A `--files=branch` selection holding no C++ reports `SKIPPED`, and
`--staged` over an empty index now *fails* outright ("the index is empty, so no file was
analyzed"). Neither means clean — nothing was examined. Read the file count in the output and
check it against how many files you touched; if it is zero and you changed C++, find out why
before reporting a clean run.

Files the profile does not compile are reported as `skipped N files absent from the compilation
database`. Treat that line as a coverage report, not noise — a module excluded by manifest is
silently linted by nothing.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
