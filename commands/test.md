---
description: Run the engine test suite via ForgePrototype. Delegates builder-readiness to /phoe:build.
---

Run the engine test suite using ForgePrototype's in-process trial runner.

## 1. Ensure the Builder Is Ready

The tests run through `forge-prototype`. Locate it (prefer the bootstrap output), bootstrapping if
absent:

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

If the engine hasn't been built yet, run `/phoe:build` first — the trial runner executes the
binaries produced by a `configure` + `build` of the test profile.

## 2. Profile

Use `forge-builds-editor` — the Headless engine profile, which has tests enabled.
`forge-builds-editor-release` has tests **disabled** and will not run trials.

## 3. Test

```bash
"$FP" test forge-builds-editor --output-on-failure
```

On success the runner prints a single summary line (`Tests: PASSED (P/T, Xs)`); passing trials are
not echoed. On failure it prints each failing trial's name and captured output. Narrow the run with
`--name=<substring>` (alias `-R`) or `--label=<APP_TRIAL|CORE_TRIAL|PLUGIN_TRIAL|BENCHMARK_TRIAL>`
when iterating on a single area.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
