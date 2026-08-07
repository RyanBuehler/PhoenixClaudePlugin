# Audit: style

## Rules

Read [`references/style-guide.md`](../../../references/style-guide.md) — the authoritative
rulebook, cited by section (`§Naming`, `§Language Features`, …) rather than by ID. Consult
`references/modern-cpp.md` and `references/cpp-portability.md` only when the file under
audit touches that territory.

Not in this sweep: comments and TODOs (`audits/comments.md`), the file preamble
(`audits/header.md`), module and subsystem boundaries (`audits/architecture.md`).

**Never load `references/formatting.md`.** Everything in it is mechanical — column width,
indentation, braces, alignment, include ordering, blank lines between definitions. A file
violating any of it is unformatted, not drifted; the finding is "run `/phoe:format`", and
it is one line, not a list.

## What to look at

Whole file. This is the broadest sweep in the set and the most expensive; prefer
`--rotation` over running it across a module in one go.

## Detection

**Formatting residue** (§Formatting Residue) — the two things the formatter cannot decide:
a missing blank line after a `}` closing a control-flow block *inside a function body*
(`SeparateDefinitionBlocks` covers definitions only), and a variable that belongs in an
`if`/`switch` init-statement rather than the enclosing scope.

**Naming** (§Naming) — member/global/static/local prefixes, the atomic-bool prefix,
abbreviations, `Old*`→`Previous*`, `Maybe*`→`Tentative*`, `Kind*`→`Type*` and
`*Kind`→`*Type`, single-letter names outside loop counters, an overlong acronym where the
spelled-out word reads better.

**Language features** (§Language Features):

```bash
grep -nE '\b(try|catch|throw|noexcept|dynamic_cast|typeid|reinterpret_cast)\b' <file>
grep -nE '\[\[deprecated\]\]|std::(move|forward)\b|std::filesystem|#include <filesystem>' <file>
```

- `Move` / `Forward` are the house spellings; `std::move` / `std::forward` should return
  zero hits in shared source.
- `std::filesystem` outside `Engine/Core/{Public,Private}/IO/` routes through `IO::File` /
  `IO::Directory` / `IO::Path`. If the wrapper lacks the operation, say so — the fix is to
  extend `IO::*`, not to bypass it. Platform OS-callback path shapes may drop to Nit.
- `static_cast` three or more times in one function is a type-design smell reported once,
  not per cast. The fix reshapes the types.
- `auto` on an error-bearing return, missing trailing return types, `const` correctness.

**Error handling** (§Error Handling) — `(void)expr`, `std::ignore =`,
`[[maybe_unused]] auto _ =` on an error-bearing return; a default-constructed `T` returned
from an `expected<T, E>` function as a silent failure.

**Design practices** (§Design Practices) — `new`/`delete`; a singleton shape (private
constructor plus a static `Get`/`Instance`); a macro with no exemption; `#ifdef`/`#if` in
shared code; a raw string used as an identity key where `Label` is required; a helper
placed outside its owning namespace.

**Namespaces** (§Code Organization) — anonymous, `Detail`/`Internal`/`Helpers`/`Utils`/
`Misc`/`Common`, or an empty one.

**Reuse** (§Reuse Before Reimplementation) — a common algorithm hand-rolled at a call site
where a `Std`/`Core`/module helper exists or should: string split or trim, hashing, byte
packing, clamp or lerp math, scratch buffers, path manipulation. Cite the existing helper,
or recommend extracting one.

## Severity

| | Rules |
|---|---|
| **Critical** | A swallowed error-bearing return; a forbidden keyword that changes semantics (`throw`, `dynamic_cast`); a default-constructed `T` standing in for a failure |
| **Warning** | Naming drift, `std::move` vs `Move`, `std::filesystem` bypass, singletons, macros, `#ifdef` in shared code, namespace names, hand-rolled boilerplate |
| **Nit** | Formatting clang-format misses, acronym length, a single-letter local |

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | `std::move`→`Move`, `std::forward`→`Forward`, blank line after `}`, `Maybe*`→`Tentative*` and `Kind`→`Type` when scoped to one declaration and its same-file references |
| **Judgment** | Renaming an abbreviation, choosing `Previous` versus a domain word, deciding whether a namespace is generically named, rewriting an accessor into an intent-based operation, swapping hand-rolled code for an existing helper |
| **Report-only** | A `static_cast` cluster, a singleton that wants to be a subsystem, a `std::filesystem` site needing `IO::*` extended, a boilerplate cluster needing a helper extracted |

Swapping hand-rolled code for a one-call helper is judgment-required, never mechanical —
behavior equivalence needs eyes.

## False positives

- A bare tool name that merely *embeds* a forbidden spelling as a substring is not a hit;
  the forbidden-token gate matches on word boundaries and so should you.
- `Engine/Modules/Platform/**` is exempt from the platform-API ban and may carry
  platform macros and lint suppressions.
- `Engine/Core/{Public,Private}/IO/` is the owner of `std::filesystem` and is exempt.
