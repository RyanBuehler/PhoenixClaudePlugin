---
description: Full CI-mirror verification sequence — configure, build, format check, lint, and test via ForgePrototype. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is incomplete work.

The phases below are the inline equivalents of `/phoe:build`, `/phoe:format`, `/phoe:lint`,
`/phoe:test`. Run them directly to avoid nested skill invocations; use the sub-skills when debugging
a single phase. The engine build/lint/test all go through `forge-prototype`; formatting stays on
`Tools/format.py` (it carries the exact branch-diff scoping CI uses).

Locate the builder once:

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

## 1. Build

```bash
"$FP" configure forge-builds-editor
"$FP" build forge-builds-editor
```

`forge-builds-editor` is the Headless, tests-enabled profile. See `/phoe:build` for builder
bootstrap and profile details. (No `--json` here: a verify-gate failure should surface the failing
node's compiler output inline — the default tier prints a bounded head+tail excerpt — rather than
report `error_count` with no error text.)

**Struct/enum layout changes need a clean build to trust.** When a change alters the in-memory
layout of a struct/enum in a header many TUs include, an incremental module build can leave some TUs
on the old layout and produce a *phantom* trial segfault near a `vector`/copy of the changed type
(an ABI/size skew, not a logic bug). For an authoritative clean engine build, remove the profile's
output tree first: `rm -rf Applications/ForgePrototype/.forge-out/shared-engine-ci-linux-Headless`,
then rebuild. Treat such a segfault as a build artifact first, a logic bug second.

## 2. Format

Use `--files=branch` to mirror CI exactly (compares against `main`). `--files=staged` silently
passes when nothing is staged.

```bash
python3 Tools/format.py --files=branch
python3 Tools/format.py --files=branch -error
```

`--files=branch` does **not** see untracked new files (they are not in the branch diff until
`git add`-ed), so a new file's formatting only surfaces after it is staged. Stage new files before
this gate (then re-check with `--files=staged`) so violations don't slip to CI.

## 3. Lint

```bash
"$FP" lint
```

ForgePrototype resolves the compile context from its own build graph — no separate compile-database
step. Lints the branch diff; pass `--all` for the whole repo.

## 4. Test

```bash
"$FP" test forge-builds-editor --output-on-failure
```

Passing trials are suppressed; failures print their name and captured output.

## Python-only changes

If the diff is 100% Python (touches no C++, build, or test code), phases 1-4 are no-ops:
`format.py`/`tidy.py` act only on C++, and `python3 Tools/format.py --files=staged -error` even
*errors* on zero staged C++ files. For a Python-only change, skip phases 1-4 and run the touched
tool's own suite instead — e.g. `python3 -m unittest discover -s Tools/Tests`. Treat "no C++ in
scope" as a clean pass, not a failure.

## 5. Report

Tell the user whether all checks passed or which step failed. If all passed, the work is cleared to
commit.
