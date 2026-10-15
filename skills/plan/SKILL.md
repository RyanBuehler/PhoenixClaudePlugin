---
name: plan
description: Brainstorm, design, and decompose a feature into a Crucible Saga with ordered, commit-sized Challenges.
disable-model-invocation: true
---

Plan a feature from idea to actionable Crucible Challenges grouped under a Saga. Accepts raw ideas (triggers brainstorming), structured plans/SDDs (skips to decomposition), or an existing saga label (extends it with new challenges).

## Arguments

- **`<saga_label>`** — *(optional)* label of an existing Saga to extend with additional Challenges

## 1. Bootstrap

Run `/phoe:build crucible` so both `crucible` and `crucible-server` exist and match the expected version. The first build is a clean build; subsequent invocations are no-ops. If `/phoe:build crucible` stops with a version mismatch, stop here and report it to the user.

**Resolve the Crucible CLI** into `$CRUCIBLE` and call it as `"$CRUCIBLE"`. Each Bash block is a fresh shell, so repeat this line in every block that calls the CLI:

```bash
CRUCIBLE=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crucible_path.py) || exit 1
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
- **Verification steps** — describe the **intent** of each verification in plain language, not the literal shell command. Write "build the editor in debug", "run the LayoutSorter tests", "confirm Aurora emits a resize event on window shrink" — never a literal invocation pinned to today's flags and output paths. The implementing agent resolves intent to the current invocation (Forge profiles, output paths), so literal commands go stale when the build system shifts. Intent must still be runnable — see spec rule 1 below.
- **Affected files** — only the files the change is expected to modify, so a reviewer can treat an
  unchanged entry as a real question. Files a reader needs only to judge the work go in
  **References** as `Context:` entries. The list is a hint, not a contract: the clean realization
  may add helper files it did not predict.
- **References** — related docs, issues, or prior work, plus the `Context: <path> — <why it matters>` entries displaced from Affected files.

### Spec rules

Check every challenge against these before step 5; the spec reviewer checks the same list.

1. **Verification is executable.** A reviewer must be able to run each entry as written and reach a
   verdict:
   - use the scoped search form (`git grep -n <pattern> -- '<pathspec>'`) — an unscoped search
     sweeps build trees and sibling worktrees;
   - name a profile that builds on the target host *and* runs the trials in question;
   - name the existing harness where one already performs the check;
   - require only steps performable against the branch;
   - mark a criterion that cannot be checked mechanically, so review effort goes to the ones that can.
2. **Criteria do not contradict each other**, within a challenge or across the saga. When two
   challenges constrain one mechanism (a threading model, a registration point, a storage layout),
   one owns it and the others refer to it ("the opt-in marker `<label>` introduces") — two
   descriptions cannot both be the design.
3. **Read each criterion literally.** Name the cheapest change that satisfies its exact words; if
   that change would be a defect, reword until it is not — a conscientious implementer follows the
   words.
4. **Cite symbols, never line numbers** — name a file plus a searchable function, type, constant or
   literal, because line numbers drift before the challenge is picked up.
5. **Every name resolves.** `git grep` each symbol and `git ls-files` each document path the plan
   names; one that resolves to nothing is a bug in the plan. Check the starting premise against the
   tree, not the design document — a design doc written before the code exists is a hypothesis, so
   every implementing challenge re-checks it.
6. **Name the couplings a build needs.** When a challenge drops a declaration from a header and
   requires consumers to compile unchanged, state where consumers get the symbol now. Name the
   wiring a first build misses: a new `Phoenix.Core` partition needs `export import :X;` in the
   `Phoenix.Core.cppm` aggregator; a new pipeline stage or registration usually goes in both a
   runtime registry list and a manifest or entry-points file; a dockable Editor panel needs
   `EditorUI.{h,cpp}` wiring; a new glob-discovered trial file needs a `forge configure` re-run.
7. **Place Mirage GPU and inference code in `Rendering::VulkanBackend`** (free functions plus
   trials), not `Rendering/Mirage` — Mirage does not depend on VulkanBackend, so GPU code there does
   not link. Mirage is already in VulkanBackend's `requires_test_module`.
8. **Spec only in-tree code** — never name a third-party library (zstd, a JSON library, torch);
   Phoenix allows only OS dependencies (X11, ALSA, Vulkan).

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
> - **Spec rules** — check each challenge against these rules: <paste step 4's "Spec rules" list verbatim>
> - **Completeness** — are description, acceptance criteria, strategy, verification, and affected_files concrete enough to brief a capable engineer who cannot ask questions? `/phoe:execute` runs these specs autonomously, so missing context is a future failure.
> - **Ambiguity** — does any criterion admit several correct implementations? Verification entries must be intent strings, never literal shell commands.
> - **Files vs context** — does `affected_files` list anything the change is not expected to modify? Context-only files belong in `references` under a `Context:` prefix.
> - **Ordering** — do dependencies implied by strategy, affected_files, or referenced symbols match the sequence? Earlier challenges must not depend on later ones, and no challenge may use a symbol, file, or concept that neither an earlier challenge nor the codebase provides.
> - **Missing context** — which file paths, prior-art references, or project conventions does the implementer need cited to ground the approach in Phoenix patterns?
> - **Scope** — is each challenge commit-sized? Is anything bundled that should split, or split that should bundle?
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

All list-style flags use `|` as the separator. Verification entries are intent strings, not literal shell commands: `"Build the editor in debug"`, `"Run the LayoutSorter tests"`, `"Confirm Aurora emits a resize event on window shrink"`. Each entry must still be executable as stated against this repository (step 4, spec rule 1).

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

**Comment on any open challenge whose ground this plan moves.** When a new challenge renames, moves,
or supersedes something an already-open challenge points at, say so on that challenge — what moved to
what name, and which behaviors introduced since must not be dropped. Its description is frozen text
written against an older tree; the comment is what tells its implementer the ground shifted at all,
and it is read as authoritative at pickup.

```bash
"$CRUCIBLE" challenge comment --label=<OPEN_LABEL> --body="<what moved; what must not be dropped>"
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
