---
description: Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges.
---

Plan a feature from idea to actionable Crucible Challenges grouped under a Saga. Accepts raw ideas (triggers brainstorming), structured plans/SDDs (skips to decomposition), or an existing saga label (extends it with new challenges).

## Arguments

- **`<saga_label>`** — *(optional)* label of an existing Saga to extend with additional Challenges

## 1. Bootstrap

Ensure `./crucible-server --headless &` is running. The CLI is a client; commands fail if the server is down.

Ensure Crucible is initialized:

```bash
./crucible status
```

If a `<saga_label>` argument was provided, verify it exists:

```bash
./crucible saga show --label=<SAGA_LABEL>
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
- **Verification steps** — commands to verify the work
- **Affected files** — files likely to be touched
- **References** — related docs, issues, or prior work

Challenges must be:
- **Commit-sized** — completable in a single focused session
- **Self-contained** — can be verified independently
- **Ordered** — respects dependencies (earlier challenges don't depend on later ones)

## 5. Review

Present the saga and all proposed challenges for review.

If extending an existing saga, show its current challenges first for context.

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

## 6. Create

After approval, create the challenges and saga using the CLI.

All list-style flags use `|` as the separator. Verification entries are flat strings (commands embedded in prose, e.g. `"Compile the build (cmake --build .)"`).

**Create each challenge:**

```bash
./crucible challenge create --title="<TITLE>" --description="<DESC>" --priority="<PRIORITY>" --tags="<T1>|<T2>" --acceptance-criteria="<C1>|<C2>" --strategy="<S1>|<S2>|<S3>" --verification="<V1>|<V2>" --affected-files="<F1>|<F2>" --references="<R1>|<R2>"
./crucible challenge move --label=<LABEL> todo
```

**Create a new saga** (if not extending):

```bash
./crucible saga create --title="<TITLE>" --description="<DESC>" --challenges="label1|label2|..." --label="<OPTIONAL_LABEL>"
```

**Extend an existing saga** (if `<saga_label>` was provided):

```bash
./crucible saga add <SAGA_LABEL> <CHALLENGE_LABEL>
```

**Verify the result:**

```bash
./crucible saga show --label=<SAGA_LABEL>
```

If `./crucible` or `./crucible-server` is missing, build with `/phoe:build` (using `-DAPPLICATION=Crucible`), then copy both binaries from `build/bin/` to the project root.

## 7. Report

Present a summary table:

| # | Label | Title | Priority | Tags |
|---|-------|-------|----------|------|
| 1 | `add-viewport-resize` | Add viewport resize | high | cpp,rendering |

Include:
- Total challenge count
- Saga label
- Reminder: use `/phoe:implement` to start working on a challenge
