---
description: Run the project's test suite using Forge. Delegates Forge-readiness to /phoe:build.
---

Run the full test suite using Forge.

## 1. Ensure Forge Is Ready

Run `/phoe:build forge`. This rebuilds Forge from scratch if it's missing, at the wrong version, or was built in a different environment (host vs container); it's a no-op otherwise. If `/phoe:build forge` stops with a version mismatch, stop here and report it to the user.

Resolve the environment suffix for subsequent invocations:

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
```

## 2. Select Profile

Detect the active profile from existing build directories:

- If `build-editor-release` exists, use `editor-release`.
- If `build-editor-debug` exists, use `editor-debug`.
- Otherwise default to `editor-debug`.

## 3. Test with Forge

```bash
PHOE_ENV=${PHOE_ENV:-$([ -f /.dockerenv ] && echo container || echo host)}
build-forge-${PHOE_ENV}-release/bin/forge test <profile> --output-on-failure
```

If the build directory for the selected profile doesn't exist, tell the user to run `/phoe:build` first.

## 4. Report

Tell the user which tests passed. If any failed, show their names and output.
