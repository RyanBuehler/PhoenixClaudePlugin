---
description: Full CI-mirror verification sequence — configure, build, format check, lint, policy audits, and test through Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is incomplete work.

`forge verify <profile>` *is* the CI mirror. The phases run **audits → tool-tests → configure →
build → format-check → lint → test**, and the audits lead deliberately: none of them reads build
output, so a drifted environment aborts in seconds instead of after a build and a clang-tidy pass.
Any non-zero phase short-circuits the rest. That single command is the gate; the sub-skills
(`/phoe:build`, `/phoe:format`, `/phoe:lint`, `/phoe:test`) exist for debugging one phase in
isolation, not for re-assembling the sequence by hand.

**Read the phase lines, not the exit code, and never `$?` alone.** Each phase prints its own tally,
and an abort prints `verify stopped at <phase>, so these phases did not run: …`. That line is the
authoritative statement of what was and was not checked. A run whose output carries no `test` tally
has tested nothing, however it exited.

**It verifies one profile, not the project** — the failure mode that has most often convinced an
agent it verified work it had not. See §2a.

## 1. Locate the Builder

Every phase runs through the bootstrapped `forge` binary. Locate it, bootstrapping if absent:

```bash
forge_bin() {
  [ -x Applications/Forge/.bootstrap-out/forge ] && { echo Applications/Forge/.bootstrap-out/forge; return 0; }
  return 1
}
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
```

Re-run `python3 Applications/Forge/Scripts/bootstrap.py` after pulling changes under
`Applications/Forge/` — a stale bootstrap binary fails cold configures cryptically. See `/phoe:build`
for bootstrap details.

## 2. Verify

```bash
"$FORGE" verify editor
```

`editor` is the Headless, tests-enabled profile CI runs against. Do **not** pass `--json` here: a
verify-gate failure should surface the failing phase's output inline — the default tier prints a
bounded head+tail excerpt and the format/lint/audit diffs — rather than reduce a failure to an
`error_count` with no error text.

**New files no longer need staging.** `forge` scopes both format-check and lint to the branch
surface (`--files=branch`), and that selection deliberately folds in untracked, non-ignored files
on top of the diff — see the comment in `Tools/git_utils.py:get_branch_files`. A brand-new
`.cpp`/`.cppm` is therefore in scope before you `git add` it. Staging is still harmless, and
remains the only way to use the opt-in `--staged` scope.

**An empty selection is not a pass.** If the gate reports zero files while you changed C++, that is
a failed run, not a clean one — find out why before believing it.

**Three shapes that read as a broken change and are not.** `forge build` failing in 0.2s with "the
source set changed since `forge configure` ran" means you added or deleted a file: Forge globs at
configure time, so `configure` first. A `FAILED` build line beside a passing test tally in the same
run means the trials ran against stale binaries — read the build line first, and never push on the
test line alone. And `forge format` takes no `--files` flag; the bare command is the whole
interface.

**Run `forge format` before you build, never after.** This is about the *manual* rewrite command, not
verify's internal `format-check` phase, which only inspects and cannot invalidate anything. A
`forge format` run after a build leaves sources newer than their trial binaries, which trips the test
phase's staleness guard and costs a full rebuild. So: `forge format` first, then verify.

### 2a. Scope — one verify covers one profile

`forge verify editor` proves nothing about any other profile. Most importantly it **does not run
Forge's own trials**: a change under `Applications/Forge/` can be green here and broken in CI. That
has happened twice, and a human caught it, not this workflow.

- A change touching the builder needs `"$FORGE" verify forge` explicitly, in addition to `editor`.
- **Adding a module manifest, or an application `requires_module` entry, invalidates Forge's
  module-metadata fixtures** (`Applications/Forge/Trials/CodeGen/Fixtures/expected_modulemetadata_forge_*.cpp`).
  Only `verify forge` builds those trials, so the editor profile reports green while CI reds. There
  is no regeneration script: diff the generated `ModuleMetadata.generated.cpp` against the fixture
  and splice in only the lines your change caused — the two renders differ in more than your change,
  so a wholesale copy is wrong. Build-free pre-check: grep both fixtures for the new module name.
- **A change that edits a build profile must verify that profile.** Do not report a set of profiles
  as verified unless each one was actually run — a dispatch brief once listed six verified profiles
  while the commit under review edited six *others*, none of which any listed run touched.
- When reporting verification to a user, a reviewer, or a PR body, name the profiles you ran. "Verify
  passed" without a profile is not a claim anyone can check.
- **`editor-debug` compiles no trials** (`tests_enabled: false`), as does `editor-release`, so a
  green debug build says nothing about trial code — one run reached a `REQUIRES` compile error only
  under `verify editor`. When a challenge says "the editor profile in debug", it still means
  `editor` for anything a trial must prove.

### 2b. Flags, and the failures that are not yours

`forge verify` takes the profile and `--build-dir`, plus the verbosity family (`--quiet`,
`--summary`). **It rejects everything else, including `--jobs`** — the flag that would cap
parallelism is exactly the one verify does not have. The rejection is instant (`error: unknown
flag: --jobs`), so with output redirected it reads as an empty log rather than a failure. Serialize
with other agents instead; there is no in-command throttle.

Two aborts that are the environment, not the change:

- **The toolchain audit** fails when the host's clang suite falls outside the window in
  `Tools/toolchain.lock.json`. It is a real gate — a `.pcm` is readable only by the clang that wrote
  it — but a drifted host is not a defect in your diff. The Vulkan entry is now a floor rather than
  an exact pin and this host satisfies it, so a brief claiming verify cannot complete here is stale.
- **A lint phase that fails naming one file with `timeout after 300s`** is usually load, not debt.
  Under concurrent agents the victim rotates run to run. Exonerate it by linting the same path alone
  — but not at the base revision if your branch changed the headers that TU includes, since the base
  file may not compile at all and tells you nothing.

**On failure**, re-run only the phase that broke to iterate faster (each maps to a sub-skill):

| Failed phase        | Iterate with                              |
|---------------------|-------------------------------------------|
| configure / build   | `"$FORGE" build editor` (`/phoe:build`)   |
| format-check        | `"$FORGE" format` then re-check (`/phoe:format`) |
| lint                | `"$FORGE" lint` (`/phoe:lint`)            |
| forbidden-token audit | fix the flagged path/token; see CLAUDE.md "Forbidden tokens" |
| toolchain audit     | usually the host outran a pinned SDK version (see §2b); genuinely yours if you edited `Tools/toolchain.lock.json` or a manifest `dependencies` block |
| trial-friend / IO-seam / heap-seam audit | run the named `Tools/audit_*.py` directly for its full output |
| test                | `"$FORGE" test editor --output-on-failure` (`/phoe:test`) |

Re-run `"$FORGE" verify editor` once the phase passes, so the full sequence confirms nothing else
regressed.

**Struct/enum layout changes need a clean build to trust.** When a change alters the in-memory
layout of a struct/enum in a widely-included header, an incremental module build can leave some TUs
on the old layout and produce a *phantom* trial segfault (an ABI/size skew, not a logic bug). For an
authoritative clean run, `"$FORGE" clean editor` first. Treat such a segfault as a build artifact
first, a logic bug second.

## 3. Python-only changes

If the diff is 100% Python (touches no C++, build, or test code), the meaningful gates
(format-check, lint) have no C++ surface to act on. For a Python-only change, run the touched tool's
own suite instead — e.g. `python3 -m unittest discover -s Tools/Tests`. Treat "no C++ in scope" as a
clean pass: if `forge verify editor` reports no files for a phase — or errors out because a phase
has an empty C++ set — that is the no-C++ signal, not a real failure.

## 4. Report

Tell the user whether all phases passed or which phase failed (with its inline output). If all
passed, the work is cleared to commit.
