# Audit: logging

## Rules

Read [`references/logging.md`](../../../references/logging.md). That document is the
rulebook (`L1`…`L32`); this file is only how to run the sweep. Also read
`references/style-guide.md` §Namespaces if the sweep touches channel declarations.

## Finding the sites

Log calls are unqualified channel functions, pulled in by a file-scope
`using namespace <Module>::Log;`:

```bash
grep -nE '\b(Trace|Log|Warn|Error|Fatal|ThrottledTrace|ThrottledWarn)\(' <file>
```

**Precision matters here.** `Error(` and `Log(` are ordinary identifiers in plenty of
contexts. Before treating a hit as a log call, confirm the TU carries a channel
using-directive, or that the call is channel-qualified. A file that logs with no
using-directive and no qualification is itself an L29 finding.

Two sweeps need the whole target set at once rather than one file at a time:

```bash
# L24 — invariant strings that appear at more than one call site
grep -rhoE '\b(Trace|Log|Warn|Error|Fatal)\("[^"]*"' <target> | sort | uniq -d

# L29/L30 — bypassing the channel entirely
grep -rnE '\bScribe::(Log|LogFormat|LogPreformatted)\(|\b(printf|fprintf)\(|std::(cout|cerr)' <target>
```

## Detection

| Rule | Spot it by |
|---|---|
| L4 name the subject | A message with no `{}` and no proper noun — "Failed to register" |
| L5 state the consequence | An `Error`/`Warn` that names a cause and stops there |
| L6 carry the error text | An `expected` unexpected branch whose log drops `.error()` |
| L7 nothing redundant | `grep -nE '(Trace\|Log\|Warn\|Error\|Fatal)\("\['` — a bracketed prefix inside the text |
| L8 units | A `{}` adjacent to a duration, size, or count word with no unit after it |
| L9 no addresses | `%p`, `(void*)`, or a pointer passed as a format argument |
| L10 one line | `\n` inside a message literal |
| L11 no terminal period | `grep -nE '\."[,)]'` on log lines |
| L12 quote identities | An interpolated `Label`/name/path with no surrounding `'…'` |
| L13 separators | A message with two clauses joined by a comma or a period |
| L14 float precision | A bare `{}` whose argument is a float or double |
| L15 literal format | `Log(format(…))` or `Warn(format(…))` — building a string to pass to the preformatted overload |
| L16 no decoration | Non-ASCII glyphs or `\033[` inside a message literal |
| L17–L22 voice | Read the literal: casing, tense, first person, `...`, length over ~100 chars |
| L23 invariant leads | `grep -nE '\("\{\}'` |
| L24 unique per site | The `uniq -d` sweep above |
| L25 self-contained | A message that only makes sense after the line before it |
| L26 stable | A counter, address, or timestamp baked into the invariant text |
| L27 right category | A module with its own channel logging to `General` |
| L28 no secrets | A token, key, password, or `/home/<user>` path in an argument |
| L29 use the channel | `Scribe::` called from module code |
| L30 no stdio | `printf` / `cout` / `cerr` in engine code |
| L31 throttle hot paths | An unthrottled call inside a loop, or in a function named `Tick`/`Update`/`Render`/`Process` |
| L32 argument cost | `Trace(` whose arguments call `Join`, `ToString`, `to_string`, `format`, or build a container |

## Severity

| | Rules |
|---|---|
| **Critical** | L28, L31, L32, and `Fatal` used where execution continues |
| **Warning** | L1–L7, L9, L10, L15, L18–L20, L23–L27, L29, L30 |
| **Nit** | L8, L11–L14, L16, L17, L21, L22 |

L31 and L32 are Critical because they cost in shipping builds, not because the message
reads badly.

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | L7 (strip the prefix), L11 (drop the period), L12 (add quotes), L16 (strip the glyph), L17 (fix case), L21 (drop the ellipsis) |
| **Judgment** | L4, L5, L6, L8, L9, L10, L13, L14, L15, L18–L20, L22–L26, L28 |
| **Report-only** | L1, L2, L3, L27, L29, L30, L31, L32 |

L28 is judgment-required *and* Critical: never redact silently, always ask.

The level rules (L1–L3) are report-only because changing a level changes what ships to
whom. Propose the change and the reason; let the owner decide.

## False positives

- `Trace("Initialized")` / `Trace("Shutdown")` appear at a great many call sites. They are
  real L24 violations, but sweeping them all at once produces a diff nobody can review.
  Report the count, fix them for the module under audit, and leave the rest.
- A `Warn` inside a loop is not automatically L31 — a loop that runs three times at
  startup is not a hot path. Check the call frequency before reporting.
- Scribe's own sources legitimately use `Scribe::` directly and prefix `[Scribe]`; they
  are the owner. Do not report L7 or L29 against `Engine/Core/{Public,Private}/Logging/`.
