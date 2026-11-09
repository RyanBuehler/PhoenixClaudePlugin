---
name: lint
description: Run clang-tidy on changed files through Forge.
---

Run clang-tidy on branch-changed C++ files through Forge's `lint` command. It reads the compile
database that `forge configure` and `forge build` emit for the profile, not the build graph. If that
database is missing or stale, run `"$FORGE" build <profile>` first.

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
"$FORGE" lint <profile> [--base=<ref>] [--no-fail-on-uncompiled]
```

This lints the **branch** surface — every C++ file differing from its merge-base with `origin/main`,
staged or not. That is the default (`--files=branch`); `--all` lints the whole repo and `--staged`
narrows to the index. `--base=<ref>` diffs the branch selection against that commit instead of the
merge-base, for example the tip of the PR a stacked branch sits on.

`<profile>` selects that profile's own compile database, `forge-<profile>.compile_commands.json` in
a shared tree, and a profile that has not been configured is refused. Without a profile, lint
resolves the sole database; once more than one tree is configured it needs `--build-dir`.

**An empty run is not a pass.** A `--files=branch` selection holding no C++ reports `SKIPPED`, and
`--staged` over an empty index now *fails* outright ("the index is empty, so no file was
analyzed"). Neither means clean — nothing was examined. Read the file count in the output and
check it against how many files you touched; if it is zero and you changed C++, find out why
before reporting a clean run.

**A changed file the profile does not compile fails the run** when another configured profile
compiles it, and the failure names that profile: run `"$FORGE" configure <profile>` if needed, then
`"$FORGE" lint <profile>` for it (`--path-include` scopes the run to its files). If the file is this
profile's own source, the database is stale; regenerate it with `"$FORGE" build <profile>`. A file
no configured profile compiles, such as another platform's source or a fixture, is named and does
not fail. A whole-tree lint neither reports these files nor fails on them.

`--no-fail-on-uncompiled` prints the same report without failing, for linting one profile of
several over the same change. `forge verify` and CI pass it, because one profile cannot compile a
cross-profile change.

CI lint is a read-only gate on a pull request's changed files: every lane that builds lints them
against its own profile's compile database, and a finding fails the job.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
