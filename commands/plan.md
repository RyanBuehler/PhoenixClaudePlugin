---
description: Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges.
---

Plan a feature from idea to actionable Crucible Challenges grouped under a Saga. Accepts raw ideas (triggers brainstorming), structured plans/SDDs (skips to decomposition), or an existing saga label (extends it with new challenges).

## Arguments

- **`<saga_label>`** — *(optional)* label of an existing Saga to extend with additional Challenges

## 1. Bootstrap

Run `/phoe:build crucible` to ensure both `crucible` and `crucible-server` exist under `build-crucible-release/bin/` and match the expected version. A fresh worktree triggers a one-time clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

Resolve the environment suffix for subsequent invocations (include this line at the top of every bash block that touches a binary):

```bash
```

The Crucible server is a user-managed process outside the plugin's scope — do not start it. If the CLI can't reach a server, the first `crucible` call below will fail with a clear error; surface that to the user and stop.

Confirm Crucible is reachable and initialized for this project:

```bash
build-crucible-release/bin/crucible status
```

If that fails with "not initialized", ask the user for the project name and run:

```bash
build-crucible-release/bin/crucible init --project="<NAME>"
```

If a `<saga_label>` argument was provided, verify it exists:

```bash
build-crucible-release/bin/crucible saga show --label=<SAGA_LABEL>
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
- **Verification steps** — describe the **intent** of each verification in plain language, not the literal shell command. Write "build the editor in debug", "run the LayoutSorter tests", "confirm Aurora emits a resize event on window shrink" — never `cmake --build build-clang/ -j24` or `ctest --test-dir build/ -R Foo`. The implementing agent resolves intent to the current invocation (Forge profiles, env-suffixed dirs, etc.), so literal commands go stale the moment the build system shifts.
- **Affected files** — files likely to be touched
- **References** — related docs, issues, or prior work

Challenges must be:
- **Commit-sized** — completable in a single focused session
- **Self-contained** — can be verified independently
- **Ordered** — respects dependencies (earlier challenges don't depend on later ones)

## 5. Subagent Spec Review

Before presenting the draft to the user, dispatch a spec reviewer subagent to audit the saga and its challenges for spec quality. The agent that drafted the plan is rarely the best judge of its own gaps — a fresh reader catches ambiguity, missing context, and ordering mistakes that the drafter has already rationalized away.

Launch `invoke-spec-reviewer` as a subagent with the prompt:

> Audit the following draft Crucible saga and challenges for **spec quality** — there is no implementation yet, so this is a forward-looking review of the contract, not a compliance check. For each challenge, evaluate:
>
> - **Completeness** — are description, acceptance criteria, strategy, verification, and affected_files concrete enough to brief a capable engineer who cannot ask questions? `/phoe:execute` runs these specs autonomously, so missing context is a future failure.
> - **Ambiguity** — are any criteria phrased so they admit multiple correct implementations, or in ways that cannot be mechanically verified? Verification entries must be intent strings, never literal shell commands.
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

All list-style flags use `|` as the separator. Verification entries are intent strings, not literal shell commands: `"Build the editor in debug"`, `"Run the LayoutSorter tests"`, `"Confirm Aurora emits a resize event on window shrink"`. Implementers resolve intent to the current invocation; literal commands like `cmake --build build/` rot when the build system shifts.

**Create each challenge:**

```bash
build-crucible-release/bin/crucible challenge create --title="<TITLE>" --description="<DESC>" --priority="<PRIORITY>" --tags="<T1>|<T2>" --acceptance-criteria="<C1>|<C2>" --strategy="<S1>|<S2>|<S3>" --verification="<V1>|<V2>" --affected-files="<F1>|<F2>" --references="<R1>|<R2>"
build-crucible-release/bin/crucible challenge move --label=<LABEL> todo
```

**Create a new saga** (if not extending):

```bash
build-crucible-release/bin/crucible saga create --title="<TITLE>" --description="<DESC>" --challenges="label1|label2|..." --label="<OPTIONAL_LABEL>"
```

**Extend an existing saga** (if `<saga_label>` was provided):

```bash
build-crucible-release/bin/crucible saga add <SAGA_LABEL> <CHALLENGE_LABEL>
```

**Verify the result:**

```bash
build-crucible-release/bin/crucible saga show --label=<SAGA_LABEL>
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
