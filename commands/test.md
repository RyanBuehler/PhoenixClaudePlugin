---
description: Run the project's test suite using Forge. Delegates Forge-readiness to /phoe:build.
---

Run the full test suite using Forge.

## 1. Ensure Forge Is Ready

Run `/phoe:build forge`. This rebuilds Forge from scratch if it's missing or at the wrong version; it's a no-op otherwise. If `/phoe:build forge` stops with a version mismatch, stop here and report it to the user.

## 2. Select Profile

Detect the active profile from existing build directories. Only pick a profile whose `BuildProfiles/<profile>.json` has `tests_enabled: true` — otherwise `forge test` will fail. Fall back to the next candidate if the first pick has tests disabled.

Candidates in priority order (first match with `tests_enabled: true` wins): `editor-debug`, `editor-release`. If none match, default to `editor-debug` and warn the user.

```bash
select_test_profile() {
  for candidate in editor-debug editor-release; do
    [ -d "build-$candidate" ] || continue
    enabled=$(python3 -c "import json,sys; print(json.load(open('BuildProfiles/$candidate.json')).get('tests_enabled', False))" 2>/dev/null)
    if [ "$enabled" = "True" ]; then
      echo "$candidate"
      return
    fi
  done
  echo "editor-debug"
}
PROFILE=$(select_test_profile)
```

Note: `editor-release` currently has `tests_enabled: false`, so it will be skipped even if `build-editor-release` exists.

## 3. Test with Forge

```bash
build-forge-release/bin/forge test "$PROFILE" --output-on-failure
```

If the build directory for the selected profile doesn't exist, tell the user to run `/phoe:build` first.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
