# Comments — Phoenix Rules

Authoritative rules for **in-source comments and TODOs**. The comment at the top of a
file is not covered here — see [`header.md`](header.md). Log message text is
[`logging.md`](logging.md).

Rules carry stable IDs (`C1`…`C20`). Cite the ID in reviews and audit findings.

Code should read as self-documenting. Reach for a comment only when the *why* is not
obvious from the code itself, or when a reader needs a nudge past something complex. A
comment is a small aid, not a technical write-up.

## §1 When to write one

**C1** — **Default to no comment.** Add one only when it tells a future reader something
the code cannot.

**C2** — **Explain *why*, not *what*.** Never restate what the code does. `// increment
counter` above `++counter;` is noise.

**C3** — **Short.** Most comments are a single line. Two or three lines is the ceiling —
if it needs more, the explanation belongs in the commit message, PR description, or a
design note, not the source.

**C4** — **Public API declarations require a comment.** Every exported class, struct,
free function, and public member function declared in a module's public header gets at
least a single-line comment describing its purpose. Prefer one line; use the multi-line
`/* … */` form only when a single line genuinely cannot convey the contract.

**C5** — A `std::memory_order` argument requires a nearby comment explaining the choice.
It is the canonical example of a non-obvious *why*.

## §2 What a comment may not contain

**C6** — **Nothing that can go stale.** No file paths, no line numbers, no symbol names
from elsewhere, no Crucible labels, no PR numbers, no branch names, no commit hashes, no
dates, no author tags. If a reader should "see also" something, the reader can grep.

**C7** — **No temporal narration.** Forbidden words include "previously", "now", "new",
"legacy", "refactored", "was", "used to". Future readers see only the current code;
commentary about what *used* to be there is noise. Why code changed belongs in the commit
message and PR description.

**C8** — **No author, date, or ticket tags.** `git blame` is authoritative.

**C9** — **No trial narration.** A production comment states the terse *why* of the code,
never a specific trial's setup or expectation; that belongs in the trial itself.

## §3 Form

**C10** — **No decorative banners.** Section headers like `// ===== Helpers =====` or
ASCII rules are forbidden. Use scope and naming instead.

**C11** — Use `//` for single-line comments. For multi-line comments use `/* … */`. Do
not stack multiple `//` lines to form a paragraph.

**C12** — **Placement.** Prefer a comment on its own line directly above the code it
explains. Trailing end-of-line comments are reserved for brief annotations — labeling an
`else` whose `if` is far above, tagging a `switch` case — and must stay short.

**C13** — American English, sentence case.

**C14** — A `// NOLINT` or `// clang-format off` carries an adjacent comment justifying
it. A bypass without a stated reason is indistinguishable from a mistake.

## §4 TODOs

TODOs are notes to a future programmer who has none of today's context. Write them so
they stay useful as the codebase moves around them.

**C15** — **Keep them short.** One line, one sentence. If a TODO needs a paragraph, the
work needs a Crucible challenge or bug, not a comment.

**C16** — **Describe the work, not the origin.** State what needs to happen, not where
the note came from.

**C17** — **No parenthesized prefix.** Write `// TODO: …`, never `// TODO(anything): …`.
The `TODO(label):` form is forbidden regardless of what the label is — Crucible labels,
saga names, PR numbers, owner handles, ticket IDs, dates, and file-path shorthand all
belong somewhere else. A grep for `TODO(` in source files should return zero hits.

**C18** — **Never reference anything that can go stale** (C6 applies with full force). All
of it drifts the moment something is renamed, rebased, squashed, archived, or merged. The
TODO should still make sense a year later when none of that context exists.

**C19** — **Do not annotate work you just did.** TODOs that explain a refactor, justify a
recent rename, or narrate a decision belong in the commit message and PR description.

**C20** — **Do not annotate trivially obvious follow-ups.** "TODO: also update the header"
is something you do now, not later.

Good:

    // TODO: handle UTF-8 surrogate pairs in token splitter

Bad:

    // TODO(execute-saga-canvas-overhaul): per code review on PR #312, see Engine/Modules/Rendering/Mosaic/Canvas.cpp:142
    // TODO: previously this used a raw pointer, switched to CanvasLease in this commit
    // TODO: address feedback from challenge `add-viewport-resize`
