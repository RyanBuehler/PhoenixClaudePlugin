---
description: Pick up a Crucible Challenge by label (or "next" for highest-priority todo) and implement it end-to-end with verification, stopping at review status.
---

Implement a Crucible Challenge end-to-end. Accepts a label or `next` to auto-pick the highest-priority todo.

## Arguments

- **`<label>`** — the challenge label to implement
- **`next`** — automatically pick the highest-priority `todo` challenge

## 1. Resolve the Challenge

If argument is `next`, query for the highest-priority todo:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.list status="todo"'
```

Pick the challenge with the highest priority (critical > high > medium > low). If tied, pick the lowest ID.

Otherwise, fetch by label:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.show label="<LABEL>"'
```

## 2. Create a Dedicated Branch

```bash
git checkout -b challenge/<label>
```

## 3. Move to In Progress

```bash
build/bin/PhoenixCrucible 'crucible.challenge.move label="<LABEL>" status="in_progress"'
```

## 4. Explore and Understand

Read the challenge description, acceptance criteria, affected files, and labels. Explore the codebase to understand what needs to change.

## 5. Plan and Implement

Enter plan mode, create an implementation plan, then execute it. Follow the project's normal development workflow — write code, follow conventions from CLAUDE.md.

## 6. Verification Gate

All verification must pass before proceeding:

**a. Challenge verification steps** — run any commands from the challenge's `verification` field (shown in the challenge JSON).

**b. Build and test** — build the project and run the test suite. Both must pass.

**c. If any verification fails** — fix the issue and re-verify. Do not proceed until everything passes.

## 7. Commit Changes

Commit all changes on the challenge branch with a descriptive message referencing the challenge label.

## 8. Report

Move the challenge to review status:

```bash
build/bin/PhoenixCrucible 'crucible.challenge.move label="<LABEL>" status="review"'
```

Tell the user:
- What was implemented
- Verification results (all passing)
- Branch name: `challenge/<label>`
- The challenge is now in `review` status — user inspects before marking done

**Do not merge or mark as done.** The user will review and decide whether to merge, request changes, or mark done.

Use `/phoe:plan` to create new challenges or extend an existing saga.

> **Note:** When the user moves a challenge to `done`, it is automatically archived to `.crucible/archive/`. If work needs to be revisited, use `crucible.challenge.unarchive label="<LABEL>"` to restore it to `todo` status.
