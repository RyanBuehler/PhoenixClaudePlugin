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

This lints the branch's changed surface (diff against `main`). Pass `--all` to lint the whole repo.
If nothing changed, it reports no files to process — treat that as a clean pass.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
