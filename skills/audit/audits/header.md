# Audit: header

The top of a file — not `.h` files. The copyright notice, the optional description, the
include guard, and the module preamble.

## Rules

Read [`references/header.md`](../../../references/header.md) (`H1`…`H26`). It cross-refers
to `references/comments.md` (C6, C7, C10, C15–C20) for what a description may not contain.

## The notice is a tool's job, not this sweep's

`Tools/copyright.py` owns H1–H6. It stamps every file with its git creation year and is
idempotent. **Never hand-edit a notice and never open a diff to add one** — run the tool:

```bash
python3 Tools/copyright.py --check     # what is missing or malformed
python3 Tools/copyright.py             # fix it
```

If a run surfaces missing notices, the finding is one line — *"N files missing a copyright
notice; run `Tools/copyright.py`"* — never a per-file list.

That leaves this sweep the parts requiring judgment: the description, the guard, and the
preamble order.

## Finding the sites

The whole audit lives in the first ~20 lines of each file, which makes this the cheapest
sweep in the set — never read a whole file for it.

```bash
head -20 <file>

grep -Ln 'pragma once' <headers>          # H17 missing
grep -ln '#ifndef.*_H' <headers>          # H18 traditional guards
```

## Detection

| Rule | Spot it by |
|---|---|
| H7 | Separator is ` — `, `: `, or a hyphen without spaces |
| H8 | Description does not end in `.` |
| H9 | Leading word does not match the filename stem |
| H10 | An acronym not all-caps (`Gltf`; `Json` excepted) |
| H11 | A partition whose subject is its module's name |
| H12 | The role describes an algorithm or a data-structure choice |
| H13 | The role restates the subject with no added information |
| H15 | Subject line wraps, or more than four comment lines before the first directive |
| H16 | Temporal words, stale paths, a banner of `=` or `-` |
| H17/H18 | `.h`/`.hpp` with no `#pragma once`, or with `#ifndef` guards |
| H19 | `#pragma once` in a `.cpp` or `.cppm` |
| H20 | `module;` with no includes under it, or preamble lines out of order |
| H22 | An `#include` below the `export module` line |
| H23 | `import Phoenix;` with no partition |

## Severity

| | Rules |
|---|---|
| **Critical** | H22 — an include attached to the wrong module is a real build hazard |
| **Warning** | H9, H11, H12, H13, H17, H18, H20, H23 |
| **Nit** | H7, H8, H10, H14, H15, H16, H19, H21 |

H1–H6 produce no severity. A missing notice is a tool that has not been run.

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | H7 (swap the separator), H8 (add the period), H10 (capitalize), H17 (add `#pragma once`), H19 (delete it), H20 (delete an empty `module;`) |
| **Judgment** | H9, H11, H12, H13, H14, H15, H16, H21, H23 — each needs a sentence written or rewritten |
| **Report-only** | H18 (guard removal changes every includer's assumptions), H22 (moving an include changes attachment and needs a build) |
| **Not yours** | H1–H6 — run `Tools/copyright.py` |

**Never write a missing description.** H7 makes it optional and H26 says its absence is not
a finding. If you know the file well enough to describe it truthfully, offer the sentence
and ask; otherwise leave it. A guessed description is worse than none, because the next
reader believes it.

## False positives

- Vendored files under `ThirdParty/`, `third_party/`, and the Wayland protocol headers
  carry foreign copyright notices. H4 exempts them completely — never report, never touch.
- A `.inl` included into a namespace body (`Logging/Log.inl`) has comments but no guard and
  no imports. Correct — H17 applies to `.h`/`.hpp` only.
- Include grouping and ordering is **never** a finding (H25). It is clang-format's, and a
  misordered block means the file is unformatted.
- A file with a notice and no description is fully compliant. Do not report it.
