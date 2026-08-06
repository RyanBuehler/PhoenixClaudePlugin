# Header — Phoenix Rules

**"Header" here means the top of a file, not a `.h` file.** Every rule below governs the
preamble every source file has: the comment that opens it, the include guard when there is
one, and the module and import lines before the first declaration.

Comments in the body are [`comments.md`](comments.md); log text is
[`logging.md`](logging.md). Rules carry stable IDs (`H1`…`H24`).

## The shape

```cpp
// ScopedProfile - RAII profiling scope marker.
// Compiles to an empty struct when profiling is disabled (true zero overhead).
module;

#include <atomic>

export module Phoenix.Diagnostics:Profiling.ScopedProfile;
import Phoenix.Core;
```

Comment, then guard or global module fragment, then the module and import lines. Then
code.

## §1 The comment

**H1** — **Every first-party source file opens with a header comment.** In scope: `.h`,
`.hpp`, `.cpp`, `.cppm`, `.ixx`, `.inl`. It is the first thing in the file, above
`module;`, above `#pragma once`, above every include.

**H2** — Trial and test files get one too, naming what is under trial.

**H3** — Vendored third-party files keep their upstream header untouched and are out of
scope entirely, as is anything under a build or generated output directory.

**H4** — The first line is `// <Subject> - <role>`. One space, hyphen, one space. Not an
em dash, not a colon.

**H5** — **Terminal period on the first line.** A header is prose describing the file and
it ends like a sentence. This is deliberately the opposite of `logging.md` L11: a log line
is a record, a header is prose.

**H6** — Use `//` line comments. Reach for `/* … */` only when the header genuinely runs
several lines, matching `comments.md` C11.

**H7** — The first line stays on one line. If the role needs more, add a blank `//` line
and continue below; never wrap the subject line.

**H8** — Follow-on lines are capped at three past the first. A file needing more
explanation than that needs a design note, or needs to be smaller.

**H9** — The subject is the file's primary export, spelled as the code spells it, matching
the filename. `Hash.cppm` opens with `Hash`, not "Consolidated Hash module partition".

**H10** — Acronyms are all-caps, per the style guide's naming rule: `GLTF`, not `Gltf`.
`Json` is the lone exception.

**H11** — A partition names its own contribution, not its module. Every partition of
`Phoenix.Diagnostics` opening with "Diagnostics" tells a reader nothing.

**H12** — Say what the file **is or does**, never how it is implemented. Implementation
belongs to the code, and a header describing the algorithm goes stale on the first
rewrite.

**H13** — **No filler restatement.** `// Color.cppm - Color.` adds nothing. If the only
honest one-liner is the filename again, the sentence to write is what the file is *for*.

**H14** — American English, sentence case after the separator.

**H15** — **No copyright, license, author, date, or ticket line.** Phoenix carries none in
first-party source, and `git blame` is authoritative for provenance.

**H16** — Everything `comments.md` forbids applies with full force: nothing that can go
stale (C6), no temporal narration (C7), no banners or ASCII rules around the header (C10).
A `// TODO:` may follow the header — it never replaces it — and obeys C15–C20.

> ✗ `// Hash.cppm`
> ✗ `// Consolidated Hash module partition: FNV-1a and WhipHash policies.`
> ✓ `// Hash - FNV-1a and WhipHash hashing policies.`

> ✗ `// Scribe - Now uses a per-category file instead of the old single log.`
> ✓ `// Scribe - Central logging subsystem with category-based filtering.`

## §2 The include guard

**H17** — Every `.h` / `.hpp` carries `#pragma once`, immediately after the header
comment.

**H18** — **No `#ifndef` / `#define` / `#endif` include guards.** They are three lines
doing one directive's work, and the macro name goes stale the moment the file is renamed.

**H19** — No `#pragma once` in a `.cpp` or `.cppm`. It means nothing in a file nobody
includes, and it implies the file is includable when it is not.

## §3 Order

**H20** — A module file reads: header comment, `module;` with its global-module-fragment
includes, `export module`, the `import` lines, then code. A `module;` block containing no
includes is noise — delete it.

**H21** — A header file reads: header comment, `#pragma once`, includes and imports, then
code.

**H22** — An `#include` placed *after* the `export module` line attaches to the module
rather than the global module. That is rarely what anyone intends; treat one as
deliberate only when a comment says why.

## §4 Imports

**H23** — Import specific `Phoenix.<Module>` partitions. There is no `import Phoenix;`
umbrella, and writing one is a design error rather than a convenience.

**H24** — Unused includes, missing includes, forward-declaration-versus-include, and
circular imports are **not** header findings. They need the include graph, which is
`invoke-lint-agent`'s job.

## What the formatter owns

Include **grouping and ordering is clang-format's**, configured in `.clang-format` with
`IncludeBlocks: Regroup`, `SortIncludes: CaseInsensitive`, and explicit `IncludeCategories`
priorities. Never report a misordered or ungrouped include as a header finding — it is not
drift, it is an unformatted file. Run `/phoe:format`.
