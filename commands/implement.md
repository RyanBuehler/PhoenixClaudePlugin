---
description: Pick up a Crucible Challenge by label (or "next" for highest-priority saga-aware todo) and implement it end-to-end with verification, stopping at review status.
---

Implement a Crucible Challenge end-to-end. Accepts a label or `next` to auto-pick the highest-priority todo respecting saga ordering.

## Arguments

- **`<label>`** — the challenge label to implement
- **`next`** — automatically pick the highest-priority `todo` challenge, respecting saga ordering

## 1. Bootstrap

Verify the Crucible binary exists:

```bash
build/bin/PhoenixCrucible 'crucible.status'
```

If this fails, tell the user to build Crucible first (`/phoe:build`) and stop.

## 2. Resolve the Challenge

**If argument is `next`**, use saga-aware selection:

1. List all sagas and their progress:

```bash
build/bin/PhoenixCrucible 'crucible.saga.list'
```

2. List all todo challenges:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.list status="todo"'
```

3. Pick the best challenge using this priority order:
   - **Saga ordering first** — if a challenge belongs to a saga, only pick it if all earlier challenges in that saga are done, canceled, or in review. Never skip ahead in a saga's ordering.
   - **Priority second** — among eligible challenges, pick the highest priority (critical > high > medium > low).
   - **Lowest ID breaks ties** — if still tied, pick the lowest ID.

4. If no eligible todo challenges exist, tell the user and stop.

**If argument is a label**, fetch by label:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.show label="<LABEL>"'
```

## 3. Show Context

Display the challenge details: title, description, acceptance criteria, and verification steps.

**Check for saga membership** — search the saga list for the resolved challenge ID. If it belongs to a saga:

```bash
build/bin/PhoenixCrucible 'crucible.saga.show label="<SAGA_LABEL>"'
```

Show the saga name, where this challenge sits in the ordering, and overall saga progress. This gives full feature context for the implementation.

## 4. Create a Dedicated Branch

```bash
git checkout -b challenge/<label>
```

## 5. Move to In Progress

```bash
build/bin/PhoenixCrucible 'crucible.challenge.move label="<LABEL>" status="in_progress"'
```

## 6. Explore and Understand

Read the challenge's affected files, references, and tags. Explore the codebase to understand what needs to change. If the challenge belongs to a saga, review completed sibling challenges for patterns and context.

## 7. Plan and Implement

Enter plan mode, create an implementation plan, then execute it. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md.

## 8. Verification Gate

All verification must pass before proceeding:

**a. Challenge verification steps** — run any commands from the challenge's `verification` field (shown in the challenge JSON).

**b. Full project verification** — run `/phoe:verify` (build + format check + lint + test). All must pass.

**c. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 9. Commit Changes

Commit all changes on the challenge branch with a descriptive message referencing the challenge label.

## 10. Report

Move the challenge to review status:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.move label="<LABEL>" status="review"'
```

If the challenge belongs to a saga, show updated saga progress:

```bash
build/bin/PhoenixCrucible 'crucible.saga.show label="<SAGA_LABEL>"'
```

Tell the user:
- What was implemented
- Verification results (all passing)
- Branch name: `challenge/<label>`
- Saga progress (if applicable)
- The challenge is now in `review` status — user inspects before marking done

**Do not merge or mark as done.** The user will review and decide whether to merge, request changes, or mark done.

Use `/phoe:plan` to create new challenges or extend an existing saga.

> **Note:** When the user moves a challenge to `done`, it is automatically archived to `.crucible/archive/`. If work needs to be revisited, use `crucible.challenge.unarchive label="<LABEL>"` to restore it to `todo` status.
