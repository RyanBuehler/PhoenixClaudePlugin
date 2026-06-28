---
description: Run clang-tidy on changed files via ForgePrototype.
---

Run clang-tidy on branch-changed C++ files through ForgePrototype's `lint` command. It resolves the
compilation context from the in-process build graph itself, so there's no separate compile-database
step (the old `Tools/tidy.py --compdb` pitfall — a bare `build/` configured with the system GCC
that hard-fails Phoenix's Clang-only gate — is gone).

## 1. Locate the Builder

```bash
fp_bin() {
  for c in Applications/ForgePrototype/.bootstrap-out/forge-prototype \
           build-fp-debug/bin/forge-prototype build-fp-release/bin/forge-prototype; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
FP=$(fp_bin) || { python3 Applications/ForgePrototype/Scripts/bootstrap.py && FP=$(fp_bin); }
```

## 2. Lint

```bash
"$FP" lint
```

This lints the branch's changed surface (diff against `main`). Pass `--all` to lint the whole repo.
If nothing changed, it reports "No files to process" — treat that as a clean pass.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
