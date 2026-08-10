---
description: Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges.
---

Plan a feature from idea to actionable Crucible Challenges grouped under a Saga. Accepts raw ideas (triggers brainstorming), structured plans/SDDs (skips to decomposition), or an existing saga label (extends it with new challenges).

## Arguments

- **`<saga_label>`** — *(optional)* label of an existing Saga to extend with additional Challenges

## 1. Bootstrap

Run `/phoe:build crucible` so both `crucible` and `crucible-server` exist and match the expected version. The first build is a clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

**Locate the Crucible CLI — discover it, don't hardcode a path.** Forge places the binary in a per-profile subtree whose name varies with host and build config, under both the configured build tree (`Applications/Forge/.forge/`) and the bootstrap output (`Applications/Forge/.forge-out/`) — take the **newest**, since a stale `.forge-out/` copy still reports a plausible version, so resolve it into `$CRUCIBLE` and use `"$CRUCIBLE"` in every crucible call below. Each Bash block is a fresh shell, so the variable will not carry across the separate blocks — re-run this `find` (or substitute the path it resolved) in each block that calls the CLI:

```bash
CRUCIBLE=$(find Applications/Forge/.forge Applications/Forge/.forge-out -type f \
    -path '*/bin/crucible' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
[ -x "$CRUCIBLE" ] || { echo "crucible not found — run /phoe:build crucible first"; exit 1; }
```

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `"$CRUCIBLE"` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
"$CRUCIBLE" status
```

If that fails with "not initialized", ask the user for the project name and run:

```bash
"$CRUCIBLE" init --project="<NAME>"
```

If a `<saga_label>` argument was provided, verify it exists:

```bash
"$CRUCIBLE" saga show --label=<SAGA_LABEL>
```

If the saga is not found, stop and tell the user.

## 2. Classify Input

Determine the input type and route accordingly:

- **SDD or structured plan** in the user's message or a referenced file → skip to **step 4** (Decompose)
- **`<saga_label>` argument** provided → enter extend mode, show existing saga challenges for context, then proceed to **step 4**
- **Raw idea or feature request** → proceed to **step 3** (Brainstorm)

## 3. Brainstorm

Invoke the `superpowers:brainstorming` skill with the user's raw idea. This explores intent, requirements, and design before implementation.

After brainstorming completes, bridge its output into:
- A **saga title** and **description** summarizing the feature
- A **requirements list** that feeds into decomposition

Proceed to **step 4**.

## 4. Decompose

Draft a saga and break the work into commit-sized, ordered Challenges.

**Saga fields:**
- **Title** — concise name for the feature
- **Description** — what this saga accomplishes and why

**For each Challenge, determine:**
- **Title** — concise action phrase (drives the auto-generated label)
- **Description** — what needs to happen, with enough context for implementation
- **Priority** — `critical` > `high` > `medium` > `low` (based on dependency order and importance)
- **Tags** — pipe-separated tags (e.g., `cpp|rendering`, `plugin|commands`, `tests`)
- **Acceptance criteria** — what "done" looks like
- **Strategy** — ordered implementation steps: patterns to follow (with file paths), functions/classes to extend, specific constraints, and step-by-step approach. Think of this as briefing a capable engineer who cannot ask questions. When creating challenges intended for `/phoe:execute`, the strategy must be thorough enough for fully autonomous implementation.
- **Verification steps** — describe the **intent** of each verification in plain language, not the literal shell command. Write "build the editor in debug", "run the LayoutSorter tests", "confirm Aurora emits a resize event on window shrink" — never `cmake --build build-clang/ -j24` or `ctest --test-dir build/ -R Foo`. The implementing agent resolves intent to the current invocation (Forge profiles, output paths, etc.), so literal commands go stale the moment the build system shifts. **Intent is not a licence to be unrunnable** — see "Verification must be executable" below.
- **Affected files** — **only the files the change is expected to modify.** Files a reader merely needs in order to judge the work go in **References**, prefixed `Context:`. The two readings of this field diverge constantly and reviewers pay for it: four separate reviews treated an unchanged entry as an implementation gap, and one was sent through sixteen hundred lines of an input file the commit never touches. With the split, a reviewer can treat an unchanged entry here as a real question and an unchanged `Context:` entry as expected. The list is still a **hint, not a contract** — the clean realization often adds helper files the list did not predict — but every entry should be a file you expect the commit to touch.
- **References** — related docs, issues, or prior work, plus the `Context: <path> — <why it matters>` entries displaced from Affected files.

**Verification must be executable.** A verification block is what settles whether the work is done,
so a reviewer must be able to run it and reach a verdict without repairing it first. Four separate
reviews hit blocks that could not be run as written. Each entry must satisfy:

- **Runnable in this repository as stated.** Use the scoped search form (`git grep -n <pattern> --
  '<pathspec>'`); an unscoped recursive search over the repo root sweeps the build trees and sibling
  agent worktrees and returns near-identical duplicates.
- **A named profile must build on the target host *and* be scoped to run the trials in question.**
  One criterion named a profile that neither builds here nor would ever run the guard trials even on
  a working machine — unsatisfiable anywhere. If a differently scoped profile expresses the intent,
  name that one.
- **Where a harness already performs the check, name the harness.** One block described packaging a
  standalone and running it from another directory — a procedure that maps one-to-one onto an
  existing harness a workflow already runs. The reviewer found it only by searching.
- **The step must be performable against the branch.** One depended on a slot no production schema
  wires, discoverable only by tracing registrations.
- **A criterion that cannot be checked mechanically says so.** Mark it explicitly, so a reviewer
  spends its effort on the criteria that can be.

Before the challenge leaves planning, read its criteria against each other for contradiction. One
challenge asked both that trials assert real relationships and that a table encode them, with
nothing saying whether the trials must bind to real code — which is the whole question of whether
they can catch a regression.

**Cite symbols, never line numbers.** Challenge descriptions and strategies must point at a file
plus a searchable name — a function, type, constant, or a distinctive literal — never `File.cpp:412`.
Line numbers drift as soon as anything above them changes, so a citation is typically stale before
the challenge is picked up and the reader has to find the thing by name anyway, which is what the
citation was supposed to save. One spec review found six cited positions in a single contract that
had all drifted against the very pre-image it was reviewing; another challenge's citations had
drifted twelve commits; a third turned a line-range read into a false finding when the offsets
disagreed with a symbol search of the same file. Symbol names do not go stale. Where a position
genuinely matters, name what is *at* that position in terms a search can find.

**Co-specified header/compile pairs.** When a challenge both drops a declaration from a header
(e.g. "remove the forward declaration of X", "stop exporting Y") *and* requires downstream
consumers to compile unchanged, name the transitive-include implication in the spec. Consumers
were likely leaning on that header to pull a symbol in indirectly, so the acceptance criteria must
state where they get it now — their own direct include, or another header. Spelling this out saves
the iteration where the implementer drops the header, breaks a transitive include, and rediscovers
the coupling at verify time.

**Mandatory cross-file couplings.** Beyond `affected_files`, name any wiring the work cannot compile
or run without — these are the recurring "first build fails" misses: a new `Phoenix.Core` partition
is invisible until re-exported from the `Phoenix.Core.cppm` aggregator (`export import :X;`); a new
pipeline stage / registration usually must be added in two places (a runtime registry list AND a
manifest/entry-points file); a dockable Editor panel needs `EditorUI.{h,cpp}` wiring; a
glob-discovered new trial file needs a `forge configure` re-run before the build sees it.

**Phoenix placement: Mirage GPU/inference code lives in VulkanBackend, not Mirage.** When
decomposing Mirage rendering/inference work, GPU passes, inference kernels, and their trials must be
specced under `Rendering::VulkanBackend` (free functions + trials), NOT `Rendering/Mirage` —
`Mirage` does not depend on `VulkanBackend`, so GPU code placed there will not link. (`Mirage` is
already in VulkanBackend's `requires_test_module`, so an e2e trial linking both needs no manifest
edit.)

**Never name a forbidden third-party library in a spec.** Phoenix uses zero third-party libraries
(no zstd/zlib, no JSON libs, no scikit-learn/scikit-image, no torch in engine code, etc.); only OS
deps (X11/ALSA/Vulkan) are allowed. A spec must not instruct the implementer to pull one in — spec
the pure in-tree approach (e.g. a hand-rolled k-means / connected-components) instead.

Challenges must be:
- **Commit-sized** — completable in a single focused session
- **Self-contained** — can be verified independently
- **Ordered** — respects dependencies (earlier challenges don't depend on later ones)

**Don't add redundant linear `block`s.** The saga's challenge *order* already encodes "do these in turn," so a challenge depending on its immediate/earlier predecessor in the same saga needs **no** `block` — rely on the ordering. Only `block` a challenge on a genuine *deviation*: a cross-saga dependency, or an out-of-order intra-saga dependency (a challenge depending on one that sits later, or left out of natural order by a re-order/insertion). See "When to block — and when NOT to" in the `crucible` skill.

## 5. Subagent Spec Review

Before presenting the draft to the user, dispatch a spec reviewer subagent to audit the saga and its challenges for spec quality. The agent that drafted the plan is rarely the best judge of its own gaps — a fresh reader catches ambiguity, missing context, and ordering mistakes that the drafter has already rationalized away.

Launch `invoke-spec-reviewer` as a subagent with the prompt. (This is a deliberate exception to the
read-only rule in `${CLAUDE_PLUGIN_ROOT}/references/dispatch-briefs.md` §1: that rule protects a live
worktree holding uncommitted code under review, and there is no such tree here — the draft exists
only in this conversation and nothing is implemented yet.)

> Audit the following draft Crucible saga and challenges for **spec quality** — there is no implementation yet, so this is a forward-looking review of the contract, not a compliance check. For each challenge, evaluate:
>
> - **Completeness** — are description, acceptance criteria, strategy, verification, and affected_files concrete enough to brief a capable engineer who cannot ask questions? `/phoe:execute` runs these specs autonomously, so missing context is a future failure.
> - **Ambiguity** — are any criteria phrased so they admit multiple correct implementations, or in ways that cannot be mechanically verified? Verification entries must be intent strings, never literal shell commands. Do any two criteria within one challenge pull against each other?
> - **Runnable verification** — can each verification entry be executed as written, in this repository, and yield a verdict? Flag unscoped searches, profiles that do not build on the target host or are not scoped to the trials named, procedures that duplicate an existing harness instead of naming it, and steps that cannot be performed against the branch at all. A criterion that cannot be checked mechanically must be marked as such.
> - **Citations** — does any description or strategy cite a line number? Every citation must name a searchable symbol instead; line numbers drift within a single challenge's lifetime.
> - **Files vs context** — does `affected_files` list anything the change is not expected to modify? Context-only files belong in `references` under a `Context:` prefix.
> - **Ordering** — do dependencies implied by strategy, affected_files, or referenced symbols match the current sequence? Earlier challenges must not depend on later ones.
> - **Missing context** — which file paths, prior-art references, or project conventions need to be cited for the implementer to ground their approach in Phoenix patterns?
> - **Scope** — is each challenge commit-sized? Is anything bundled that should split, or split that should bundle?
> - **Cross-challenge coherence** — does any challenge reference a symbol, file, or concept not introduced by an earlier challenge in this saga and not already present in the codebase?
>
> Report findings as a per-challenge punch list with severity: **BLOCKER** (spec is unusable as written), **CONCERN** (spec is risky and should be revised), or **SUGGESTION** (refinement).

Read the report. For every BLOCKER and CONCERN, revise the affected challenge fields before continuing. Apply SUGGESTIONs at your judgment. If the reviewer flags an ordering or scope issue that requires re-decomposing, return to step 4 and re-run this review on the revised draft. Record which challenges were revised and the gist of each change — surface this in the step 6 review summary so the user sees what the audit caught.

## 6. Review

Present the saga and all proposed challenges for review.

If extending an existing saga, show its current challenges first for context.

If the step 5 audit produced revisions, lead with a brief summary of what the spec reviewer caught and which challenges were updated in response. The user should see the revised draft, not the pre-audit draft, but should know what changed since they last saw it.

**Saga:**

| Field | Value |
|-------|-------|
| Title | ... |
| Description | ... |

**Challenges:**

| # | Title (→ label) | Priority | Tags | Key acceptance criteria | Strategy summary |
|---|-----------------|----------|--------|------------------------|------------------|
| 1 | ... | ... | ... | ... | ... |

Ask the user to confirm, adjust, add, remove, or reorder challenges before proceeding. Only create after the user approves.

If only a single challenge results, offer to create just a standalone challenge without a saga.

## 7. Create

After approval, create the challenges and saga using the CLI.

All list-style flags use `|` as the separator. Verification entries are intent strings, not literal shell commands: `"Build the editor in debug"`, `"Run the LayoutSorter tests"`, `"Confirm Aurora emits a resize event on window shrink"`. Implementers resolve intent to the current invocation; literal commands like `cmake --build build/` rot when the build system shifts. Each entry must still be executable as stated against this repository (see step 4).

`--affected-files` carries only files the change is expected to modify. Context files go into `--references` as `Context: <path> — <why>`.

**Create each challenge:**

```bash
"$CRUCIBLE" challenge create --title="<TITLE>" --description="<DESC>" --priority="<PRIORITY>" --tags="<T1>|<T2>" --acceptance-criteria="<C1>|<C2>" --strategy="<S1>|<S2>|<S3>" --verification="<V1>|<V2>" --affected-files="<F1>|<F2>" --references="<R1>|<R2>"
"$CRUCIBLE" challenge move --label=<LABEL> todo
```

**Create a new saga** (if not extending). `--challenges=...` is **silently ignored** on
`saga create`, so create the saga first, then attach each challenge with `saga add`:

```bash
"$CRUCIBLE" saga create --title="<TITLE>" --description="<DESC>" --label="<OPTIONAL_LABEL>"
for LBL in label1 label2 ...; do
  "$CRUCIBLE" saga add <SAGA_LABEL> "$LBL"
done
```

**Extend an existing saga** (if `<saga_label>` was provided):

```bash
"$CRUCIBLE" saga add <SAGA_LABEL> <CHALLENGE_LABEL>
```

**Verify the result:**

```bash
"$CRUCIBLE" saga show --label=<SAGA_LABEL>
```

## 8. Report

Present a summary table:

| # | Label | Title | Priority | Tags |
|---|-------|-------|----------|------|
| 1 | `add-viewport-resize` | Add viewport resize | high | cpp,rendering |

Include:
- Total challenge count
- Saga label
- Reminder: use `/phoe:implement` to start working on a challenge
