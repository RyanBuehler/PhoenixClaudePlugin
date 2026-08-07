# Header — Phoenix Rules

**"Header" here means the top of a file, not a `.h` file.** Every rule below governs the
preamble every source file has: the copyright notice that opens it, the optional
description under it, the include guard when there is one, and the module and import lines
before the first declaration.

Comments in the body are [`comments.md`](comments.md). Rules carry stable IDs (`H1`…`H26`).

## The shape

```cpp
// Copyright (c) 2025 Ryan Buehler. All rights reserved.

// ScopedProfile - RAII profiling scope marker.
// Compiles to an empty struct when profiling is disabled (true zero overhead).
module;

#include <atomic>

export module Phoenix.Diagnostics:Profiling.ScopedProfile;
import Phoenix.Core;
```

Notice, then description, then guard or global module fragment, then the module and import
lines. Only the notice is required.

## §1 The copyright notice — required

**H1** — **Every first-party source file opens with the notice, on line 1**, above the
description, above `module;`, above `#pragma once`, above every include:

```cpp
// Copyright (c) <year> Ryan Buehler. All rights reserved.
```

In scope: `.h`, `.hpp`, `.cpp`, `.cppm`, `.ixx`, `.inl`.

**H2** — **The year is the file's creation year**, taken from git history, and it is never
updated afterward. A file added in 2025 says 2025 forever. Bumping a year on edit produces
diff noise in every commit and a repo-wide churn every January, and buys nothing.

**H3** — One `//` line. Not a block comment, not a box, no ASCII rule above or below it.

**H4** — **Never rewrite someone else's copyright.** Vendored and third-party files keep
their upstream notice untouched — Wayland protocol headers, Khronos headers, `volk`, the
Android glue. A file carrying a foreign notice is left alone entirely.

**H5** — Generated code and build output are out of scope.

**H6** — The notice is maintained by `Tools/copyright.py`, not by hand. Run it after adding
a file; `--check` runs in CI and fails on a missing or malformed notice.

## §2 The description — optional

A description line is worth writing and nothing enforces it. A file without one is **not**
a finding. These rules govern the ones that exist.

**H7** — The form is `// <Subject> - <role>.` — one space, hyphen, one space — separated
from the notice by a blank line. The notice is a legal statement and the description is
about the code; they are not one paragraph.

**H8** — Terminal period. It is a sentence describing the file, and it ends like one.

**H9** — The subject is the file's primary export, spelled as the code spells it, matching
the filename. `Hash.cppm` says `Hash`, not "Consolidated Hash module partition".

**H10** — Acronyms are all-caps, per the style guide's naming rule: `GLTF`, not `Gltf`.
`Json` is the lone exception.

**H11** — A partition names its own contribution, not its module. Every partition of
`Phoenix.Diagnostics` opening with "Diagnostics" tells a reader nothing.

**H12** — Say what the file **is or does**, never how it is implemented. Implementation
belongs to the code, and a description of the algorithm goes stale on the first rewrite.

**H13** — **No filler restatement.** `// Color - Color.` adds nothing. If the only honest
one-liner is the filename again, write nothing — the description is optional precisely so
that no one has to pad.

**H14** — American English, sentence case after the separator.

**H15** — The subject line stays on one line. If the role needs more, add a blank `//` line
and continue below; never wrap the subject line. Cap the continuation at three lines.

**H16** — Everything `comments.md` forbids applies with full force: nothing that can go
stale (C6), no temporal narration (C7), no banners (C10). A `// TODO:` may follow the
description — never replace it — and obeys C15–C20.

> ✗ `// Hash.cppm`
> ✗ `// Consolidated Hash module partition: FNV-1a and WhipHash policies.`
> ✓ `// Hash - FNV-1a and WhipHash hashing policies.`

> ✗ `// Scribe - Now uses a per-category file instead of the old single log.`
> ✓ `// Scribe - Central logging subsystem with category-based filtering.`

## §3 The include guard

**H17** — Every `.h` / `.hpp` carries `#pragma once`, after the header comments.

**H18** — **No `#ifndef` / `#define` / `#endif` include guards.** Three lines doing one
directive's work, and the macro name goes stale the moment the file is renamed.

**H19** — No `#pragma once` in a `.cpp` or `.cppm`. It means nothing in a file nobody
includes, and it implies the file is includable when it is not.

## §4 Order

**H20** — A module file reads: notice, description, `module;` with its global-module-fragment
includes, `export module`, the `import` lines, then code. A `module;` block containing no
includes is noise — delete it.

**H21** — A header file reads: notice, description, `#pragma once`, includes and imports,
then code.

**H22** — An `#include` placed *after* the `export module` line attaches to the module
rather than the global module. That is rarely what anyone intends; treat one as deliberate
only when a comment says why.

## §5 Imports

**H23** — Import specific `Phoenix.<Module>` partitions. There is no `import Phoenix;`
umbrella, and writing one is a design error rather than a convenience.

**H24** — Unused includes, missing includes, forward-declaration-versus-include, and
circular imports are **not** header findings. They need the include graph, which is
`invoke-lint-agent`'s job.

## §6 Not header findings

**H25** — Include **grouping and ordering** is clang-format's, configured in
`.clang-format`. A misordered include means the file is unformatted, not drifted. Run
`/phoe:format`.

**H26** — A missing description is not a finding (H7). Report the count if it is
informative; never open a diff to add one.
