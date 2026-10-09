---
name: test
description: Run the engine test suite through Forge's in-process trial runner. Delegates builder-readiness to /phoe:build.
---

Run the engine test suite using Forge's in-process trial runner.

## 1. Ensure the Builder Is Ready

The tests run through the bootstrapped `forge` binary. Locate it, bootstrapping if absent:

```bash
forge_bin() {
  [ -x Applications/Forge/.bootstrap-out/forge ] && { echo Applications/Forge/.bootstrap-out/forge; return 0; }
  return 1
}
FORGE=$(forge_bin) || { python3 Applications/Forge/Scripts/bootstrap.py && FORGE=$(forge_bin); }
```

If the engine hasn't been built yet, run `/phoe:build` first — the trial runner executes the
binaries produced by a `configure` + `build` of the test profile.

## 2. Profile

Use `editor` — the debug engine profile, which has tests enabled. Its build type does not decide
whether a display is available. `editor-release` has tests
**disabled** and will not run trials.

## 3. Test

```bash
"$FORGE" test editor --output-on-failure
```

On success the runner prints a single summary line; passing trials are not echoed. On failure it
prints each failing trial's name and captured output. Narrow the run with `--name=<substring>`
(alias `-R`) or `--label=<APP_TRIAL|CORE_TRIAL|PLUGIN_TRIAL|BENCHMARK_TRIAL>` when iterating on a
single area.

**`--name` matches a trial *binary* name by substring** — not a trial name, not a case name, and
not a regex, so an alternation pattern matches nothing. The runner says so on a zero match and
suggests near names; act on that text rather than concluding the suite is red.

**`forge test` does not build.** It checks the configured source inventory and successful-build
state, then the runner checks binary staleness and writer identity. Missing configuration,
added/deleted files, failed builds, stale binaries, or foreign writers cause refusal rather than
proof of current code. Configure after inventory changes (including a merge), build successfully,
then test. Source collection happens at configure; a new file needs that step to enter the graph.

**Three claims a green run does not support**, each of which has shipped an unverified acceptance
criterion:

- **The headline count is binaries, not cases.** Adding a `UNIT_TRIAL` to an existing binary leaves
  `619/619` unchanged while the case count moves. Confirm a specific new trial ran by name.
- **A skipped case counts as a pass.** `--require-executed-cases` fails a trial whose cases skipped
  instead of running; pass it whenever a criterion rests on a trial executing. A skip-count jump
  (say 8 → 153) is a symptom to explain — usually load starving device init — not a host fact.
- **A green suite does not mean the assertions bite.** Follow the
  [negative-control protocol](../../references/negative-controls.md). Each claimed behavior needs
  an independently observable witness on its actual production path; a red suite alone is insufficient.

`--list-cases` lists every case that ran, skips and failures marked, without the subsystem trace; it
is the cheapest way to answer "did my case execute".

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
