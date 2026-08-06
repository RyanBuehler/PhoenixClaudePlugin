# Audit: comments

## Rules

Read [`references/comments.md`](../../../references/comments.md) (`C1`…`C20`). The header
comment at the top of a file is **not** part of this sweep — that is
`audits/header.md`. Skip line 1 and any comment block above the first directive.

## Finding the sites

```bash
grep -nE '(^|[^:"])//|/\*' <file>      # comment lines, minus most URLs
grep -n 'TODO' <file>
```

Two whole-target sweeps:

```bash
# C17 — the parenthesized TODO form; this should return zero hits engine-wide
grep -rn 'TODO(' <target>

# C10 — decorative banners
grep -rnE '//\s*[=*#-]{4,}' <target>
```

## Detection

| Rule | Spot it by |
|---|---|
| C1/C2 | A comment restating its line — `// increment counter` above `++counter` |
| C3 | Four or more comment lines in one block |
| C4 | An exported declaration in a public header with no comment above it |
| C5 | `memory_order_` with no comment on or above the line |
| C6 | A path, `:%d` line number, `PR #`, commit hash, or Crucible label inside a comment |
| C7 | "previously", "now", "new", "legacy", "refactored", "was", "used to" |
| C8 | `@author`, a date, or a ticket ID |
| C9 | A production comment naming a trial, fixture, or expected value |
| C10 | The banner sweep above |
| C11 | Two or more consecutive `//` lines forming a paragraph |
| C12 | A long trailing comment past the code on the same line |
| C14 | `NOLINT` or `clang-format off` with no adjacent justification |
| C15 | A TODO running more than one line |
| C16 | A TODO describing where it came from rather than what to do |
| C17 | The `TODO(` sweep above |
| C19 | A TODO narrating the current change |
| C20 | A TODO for something doable in the same edit |

## Severity

| | Rules |
|---|---|
| **Critical** | none — a comment never breaks a build |
| **Warning** | C2, C4, C5, C6, C7, C8, C9, C14, C16, C17, C18, C19 |
| **Nit** | C1, C3, C10, C11, C12, C13, C15, C20 |

C5 and C14 sit at Warning rather than Nit: both mark a place where a reader cannot
reconstruct the author's reasoning, and that is how a correct-looking line becomes a bug.

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | C10 (delete the banner), C11 (join into `/* … */`), C17 (strip the parenthetical), C8 (delete the tag) |
| **Judgment** | C1, C2, C3, C6, C7, C9, C12, C13, C15, C16, C19, C20 — deleting a comment is a claim that it carried nothing |
| **Report-only** | C4 (writing an API contract needs the API's author), C5 (the *why* of a memory order is not inferable), C14, C18 |

Deleting a comment is never as safe as it looks. A `// increment counter` is noise, but a
comment that *looks* redundant may be the only record of a constraint. When the comment
says anything the code does not, ask.

## False positives

- Commented-out code is not a comment finding. It is dead code; report it as such and let
  the user decide, or leave it to `invoke-code-reviewer`.
- Doxygen-style `///` or `/** */` blocks in a public header satisfy C4 — the rule asks for
  a purpose comment, not a particular syntax.
- C7's forbidden words fire constantly in false-positive contexts: "was" inside an English
  sentence about *current* behavior is fine. Read the sentence; the rule targets narration
  of the file's history, not the past tense.
- URLs contain `//`. Anchor the grep or filter them out.
