# Audit: header

The top of a file — not `.h` files. Every source file has a preamble; this sweep reads it.

## Rules

Read [`references/header.md`](../../../references/header.md) (`H1`…`H24`). It cross-refers
to `references/comments.md` (C6, C7, C10, C11, C15–C20) for what a header may not contain;
read that too if the target has TODOs or stale references in its preamble.

## Finding the sites

The whole audit lives in the first ~20 lines of each file, which makes this the cheapest
sweep in the set — never read a whole file for it.

```bash
head -20 <file>
```

Two whole-target sweeps:

```bash
# H1 — files with no header comment at all
for f in <files>; do head -1 "$f" | grep -q '^\(//\|/\*\)' || echo "$f"; done

# H17/H18 — guard drift
grep -Ln 'pragma once' <headers>          # missing
grep -ln '#ifndef.*_H' <headers>          # traditional guards
```

## Detection

| Rule | Spot it by |
|---|---|
| H1 | First line is not `//` or `/*` |
| H4 | First line separator is ` — `, `: `, or `-` without spaces |
| H5 | First line does not end in `.` |
| H7 | Subject line wraps onto a continuation |
| H8 | More than four comment lines before the first directive |
| H9 | Leading word does not match the filename stem |
| H10 | An acronym in the subject that is not all-caps (`Gltf`, `Json` excepted) |
| H11 | A partition whose subject is its module's name |
| H12 | The role sentence describes an algorithm or data structure choice |
| H13 | The role restates the subject with no added information |
| H15 | `Copyright`, `SPDX`, `@author`, a date, or a ticket ID |
| H16 | Temporal words, stale paths, a banner line of `=` or `-` |
| H17/H18 | `.h`/`.hpp` with no `#pragma once`, or with `#ifndef` guards |
| H19 | `#pragma once` in a `.cpp` or `.cppm` |
| H20 | `module;` with no includes under it, or preamble lines out of order |
| H22 | An `#include` below the `export module` line |
| H23 | `import Phoenix;` with no partition |

## Severity

| | Rules |
|---|---|
| **Critical** | H22 — an include attached to the wrong module is a real build hazard |
| **Warning** | H1, H9, H11, H12, H13, H15, H16, H17, H18, H20, H23 |
| **Nit** | H2, H4, H5, H7, H8, H10, H14, H19, H21 |

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | H4 (swap the separator), H5 (add the period), H10 (capitalize), H15 (delete the line), H17 (add `#pragma once`), H19 (delete it), H20 (delete an empty `module;`) |
| **Judgment** | H1, H7, H8, H9, H11, H12, H13, H14, H16, H21, H23 — all of them require writing or rewriting a sentence |
| **Report-only** | H18 (guard removal touches every includer's assumptions), H22 (moving an include changes attachment; needs a build) |

Writing a missing header (H1) is judgment-required, always. Never invent a role sentence
for a file whose purpose you inferred from its name alone — read enough of the file to
say something true, or leave it and report it.

## False positives

- **H1 fires on 29% of the tree** (779 of 2714 first-party files at last count). That is a
  real backlog, not a bug in the rule — but never sweep it wholesale. Fix the module under
  audit, report the engine-wide count once, and move on.
- Vendored files under `ThirdParty/`, `third_party/`, and the Wayland protocol headers
  carry upstream copyright banners. They are H3-exempt; do not report H15 against them.
- A `.inl` included into a namespace body (`Logging/Log.inl`) has a header comment but no
  guard and no imports. That is correct — H17 applies to `.h`/`.hpp` only.
- Include grouping and ordering is **never** a finding here. It is clang-format's, and a
  misordered block means the file is unformatted. Say so and run `/phoe:format`.
