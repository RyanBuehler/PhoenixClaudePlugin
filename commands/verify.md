---
description: Full CI-mirror verification sequence — configure, build, format check, lint, policy audits, and test through Forge. The mandatory pre-commit check.
---

Run the full CI-mirror verification sequence. Stop on the first failure.

Run this **before committing**. A commit made without passing verification is incomplete work.

`forge verify <profile>` *is* the CI mirror: it runs configure → build → format-check → lint →
**policy audits** → test in one in-process pass, exactly as CI does. The audits are five, run in a
fixed order — forbidden-token, **toolchain**, trial-friend, IO-seam, heap-seam — and any one of them
short-circuits the run before `test`. That single command is the
gate; the sub-skills (`/phoe:build`, `/phoe:format`, `/phoe:lint`, `/phoe:test`) exist for debugging
one phase in isolation, not for re-assembling the sequence by hand.

Two things it is **not**, both of which have convinced agents they verified work they had not:

- **It verifies one profile, not the project.** See §2a.
- **On this host it does not reach its test phase.** See §2b.

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

**Stage new files first.** `forge` scopes format-check to the branch diff and lint to the staged
surface — neither sees an untracked new file. A `.cpp`/`.cppm` you have not `git add`-ed is invisible
to this gate, so its formatting/lint violations sail through locally and fail CI. `git add` new files
before running verify so they are in scope.

**Run `forge format` before you build, never after.** This is about the *manual* rewrite command, not
verify's internal `format-check` phase, which only inspects and cannot invalidate anything. A
`forge format` run after a build leaves sources newer than their trial binaries, which trips the test
phase's staleness guard and costs a full rebuild. So: `forge format` first, then verify.

### 2a. Scope — one verify covers one profile

`forge verify editor` proves nothing about any other profile. Most importantly it **does not run
Forge's own trials**: a change under `Applications/Forge/` can be green here and broken in CI. That
has happened twice, and a human caught it, not this workflow.

- A change touching the builder needs `"$FORGE" verify forge` explicitly, in addition to `editor`.
- **A change that edits a build profile must verify that profile.** Do not report a set of profiles
  as verified unless each one was actually run — a dispatch brief once listed six verified profiles
  while the commit under review edited six *others*, none of which any listed run touched.
- When reporting verification to a user, a reviewer, or a PR body, name the profiles you ran. "Verify
  passed" without a profile is not a claim anyone can check.

### 2b. Host reality — verify aborts before its test phase

On this machine `forge verify` **does not complete**: it aborts at the **toolchain audit** — the
second of the five policy audits, and a different phase from the forbidden-token audit — on a Vulkan
pin drift, after having paid for the full lint, and yields no test result. The failure reads
`error: vulkan: version <installed> but the pin is <pinned>`. This is a known ordering
defect in Forge, tracked separately; until it lands, treat verify as a two-command sequence and do
not read an abort at the audit as a failure of the change:

```bash
"$FORGE" verify editor     # expect: aborts at the toolchain audit, after lint
"$FORGE" test editor       # the test result verify never produced
```

A run that stopped at the audit has **not** tested anything. Do not report it as a passing verify.

**On failure**, re-run only the phase that broke to iterate faster (each maps to a sub-skill):

| Failed phase        | Iterate with                              |
|---------------------|-------------------------------------------|
| configure / build   | `"$FORGE" build editor` (`/phoe:build`)   |
| format-check        | `"$FORGE" format` then re-check (`/phoe:format`) |
| lint                | `"$FORGE" lint` (`/phoe:lint`)            |
| forbidden-token audit | fix the flagged path/token; see CLAUDE.md "Forbidden tokens" |
| toolchain audit     | the host outran a pinned SDK version — not caused by your change; see §2b |
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
