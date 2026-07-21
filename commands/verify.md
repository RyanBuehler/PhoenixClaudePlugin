---
description: Full CI-mirror verification sequence — configure, build, format check, lint, forbidden-token audit, and test through Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is incomplete work.

`forge verify <profile>` *is* the CI mirror: it runs configure → build → format-check → lint →
forbidden-token audit → test in one in-process pass, exactly as CI does. That single command is the
gate; the sub-skills (`/phoe:build`, `/phoe:format`, `/phoe:lint`, `/phoe:test`) exist for debugging
one phase in isolation, not for re-assembling the sequence by hand.

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

**On failure**, re-run only the phase that broke to iterate faster (each maps to a sub-skill):

| Failed phase        | Iterate with                              |
|---------------------|-------------------------------------------|
| configure / build   | `"$FORGE" build editor` (`/phoe:build`)   |
| format-check        | `"$FORGE" format` then re-check (`/phoe:format`) |
| lint                | `"$FORGE" lint` (`/phoe:lint`)            |
| forbidden-token audit | fix the flagged path/token; see CLAUDE.md "Forbidden tokens" |
| test                | `"$FORGE" test editor --output-on-failure` (`/phoe:test`) |

Re-run `"$FORGE" verify editor` once the phase passes, so the full sequence confirms nothing else
regressed.

**Struct/enum layout changes need a clean build to trust.** When a change alters the in-memory
layout of a struct/enum in a widely-included header, an incremental module build can leave some TUs
on the old layout and produce a *phantom* trial segfault (an ABI/size skew, not a logic bug). For an
authoritative clean run, `"$FORGE" clean editor` first. Treat such a segfault as a build artifact
first, a logic bug second.

## 3. Python-only changes

If the diff is 100% Python (touches no C++, build, or test code), the format-check and lint phases
have no C++ surface to act on and the build is a fast no-op. For a Python-only change, run the
touched tool's own suite instead — e.g. `python3 -m unittest discover -s Tools/Tests` — and treat
"no C++ in scope" as a clean pass, not a failure.

## 4. Report

Tell the user whether all phases passed or which phase failed (with its inline output). If all
passed, the work is cleared to commit.
