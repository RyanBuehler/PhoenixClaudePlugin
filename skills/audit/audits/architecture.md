# Audit: architecture

## Rules

Read `CLAUDE.md` at the plugin root — module versus subsystem, the ownership tiers,
boundary data flow, subsystem interface design, color values, labels. Also read any
`CLAUDE.md` at the engine repo root or nested under the target's directory; a nested one
may strengthen rules for its subtree.

Not in this sweep: include-graph and module-import correctness (`invoke-lint-agent`), UI
and Mosaic architecture (`ui-design-review`).

## What to look at

Public headers and subsystem interfaces first — that is where a boundary violation is
declared. A `.cpp` can only violate a boundary its header already opened.

## Detection

**Ownership tiers.** Every system has one owner that drives it through its concrete
interface (Tier 1); everyone else reaches it through a registry-discovered subsystem that
names no concrete type (Tier 2).

```bash
# A concrete module type crossing a boundary — parameter, member, or return
grep -nE '\b[A-Z][A-Za-z]*Module\s*[&*]|shared_ptr<[A-Z][A-Za-z]*Module>' <file>
```

A `FooModule&`, `FooModule*`, or `shared_ptr<FooModule>` appearing outside `FooModule`'s
own files is a Tier violation. So is a subsystem header that declares a new type, or names
a concrete one in its interface.

**Boundary data flow.** A caller submits a self-contained description of the work it wants
realized; the owner realizes it. Findings:

- A component handing a system a reference to itself so it can be called back or "made
  ready" — inverted dependency.
- An owner handing a foreigner a capability the foreigner then calls back into.
- Readiness or lifecycle driven by a foreign object reaching in.
- A live self-registering object where a per-tick declarative snapshot belongs.

**Subsystem interfaces.** A `GetX()` lazy accessor; a method with no corresponding
operation on the underlying module; a public accessor returning a reference to an owned
internal.

**Singletons.** A new global singleton or static `Get()` accessor — the registry or an
owner-injected closure replaces it.

**Color** — a literal in 0–255 or hex form that was never normalized to 0–1; a hardcoded
`RGBA{…}` duplicating an existing `Color::`/`Palette::` constant; a themable UI element
colored by literal instead of by the active theme.

**Platform coupling** — a platform name (`Wayland`, `X11`, `Windows`, `Win32`, `macOS`,
`POSIX`) in an identifier, type, branch, or include outside `Engine/Modules/Platform/`.
Preprocessor guards outside the platform and Vulkan modules.

## Severity

| | Rules |
|---|---|
| **Critical** | A concrete system handed to foreign code; an inverted dependency where a foreigner drives an owner's lifecycle; platform coupling outside Platform |
| **Warning** | A subsystem method with no backing module operation, a `GetX()` accessor, an accessor leaking an owned internal, a new singleton, an unnormalized color |
| **Nit** | A color literal duplicating a named constant |

## Fix buckets

Nearly everything here is **report-only**. An architecture finding is a cross-file
refactor by definition — it touches an interface, its owner, and every caller.

| | Rules |
|---|---|
| **Mechanical** | Normalizing a 0–255 color literal to 0–1; swapping a duplicated literal for the named `Color::`/`Palette::` constant |
| **Judgment** | Replacing a themable literal with the active theme's field |
| **Report-only** | Every tier violation, every inversion, every singleton, every subsystem interface change |

For a report-only finding, name the follow-up in the terms the fix would take: *extend the
subsystem interface*, *push the logic forward and return a value*, *give this system a
designated owner*. A finding that only says "this is wrong" is half a finding.

## False positives

- **A system with genuinely diffuse ownership is Tier-2-only**, not a violation. The
  owner/subsystem split needs a single clear owner; do not demand one where none exists.
- `FooModule` inside `FooModule`'s own translation units is Tier 1 and correct by
  definition. Check the path before reporting.
- The registry itself, and `Subsystem::Find*` call sites, legitimately name subsystem
  types. That is the mediated path working.
