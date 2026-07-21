---
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

Use `editor` — the Headless engine profile, which has tests enabled. `editor-release` has tests
**disabled** and will not run trials.

## 3. Test

```bash
"$FORGE" test editor --output-on-failure
```

On success the runner prints a single summary line; passing trials are not echoed. On failure it
prints each failing trial's name and captured output. Narrow the run with `--name=<substring>`
(alias `-R`) or `--label=<APP_TRIAL|CORE_TRIAL|PLUGIN_TRIAL|BENCHMARK_TRIAL>` when iterating on a
single area.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
