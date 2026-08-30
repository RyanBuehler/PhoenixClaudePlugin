# Style Guide — agent supplement

The repository's `Docs/StyleGuide.md` is the contributor style guide and it binds. This file
does not restate it. What follows are the rules an agent gets wrong often enough to be worth
carrying in the plugin: habits imported from header-only C++, from ABI-stable library projects,
or from codebases whose conventions Phoenix does not share.

Read `Docs/StyleGuide.md` for formatting, naming, `auto`, namespaces, comments, TODOs, error
handling, and design practices. Read this for the rest.

## Language Features

### `static_cast` proliferation

Three or more `static_cast`s in one function or file is a type-design smell — one side of the
conversion is the wrong type. Fix the types: tighten the source, add a wrapper or `enum class`,
or move the conversion to a single boundary. This is a heuristic, not a ban. One cast at an API
boundary is fine; the signal is the *proliferation*.

### `Move` / `Forward`

Use the project's `Move()` and `Forward()` (exported from `Std`, `Engine/Core/Public/Std.cppm`)
rather than `std::move` and `std::forward`. They add a `[[nodiscard]]` return and a
`const`-rejecting `static_assert` that catches miscasts the standard helpers let through, and
the unqualified `std::` spellings resolve unreliably across module boundaries. The `std::` forms
should not appear in new code.

### Filesystem

Use `IO::File` / `IO::Directory` / `IO::Path` (`Engine/Core/Public/IO/`). `std::filesystem`
elsewhere is a hole in the single filesystem seam, and `Tools/audit_io_seam.py` fails over it —
including the bare `filesystem::` spelling and an `fs::` alias. If the wrapper lacks an
operation, extend it rather than bypassing it at the call site.

Exempt: the wrapper's own implementation under `Engine/Core/{Public,Private}/IO/`, and platform
code where an OS API demands a `std::filesystem::path` shape. The ban targets the *operations*,
not the path type at an unavoidable boundary.

### Return type syntax

Write the return type first (`Texture LoadTexture(...)`), not trailing (`auto LoadTexture(...)
-> Texture`). Trailing syntax is reserved for the cases that require it — a return type that
depends on the parameters, such as one deduced through `decltype`.

### Init-statements in conditions

When a variable exists only to be checked immediately, declare it in the condition so its scope
matches its purpose:

```cpp
// Prefer:
if (Subscriber* Found = Registry.Find(Id); !Found)
{
	return;
}

// Instead of:
Subscriber* Found = Registry.Find(Id);
if (!Found) { return; }
```

Spell the type — `Docs/StyleGuide.md` §`auto` applies inside the init-statement too. If the
initializer is long enough that the combined line becomes hard to read, split it back apart.
Readability wins over compactness.

### Module imports

Import the specific `Phoenix.<Module>` partitions a translation unit uses. There is no
`import Phoenix;` umbrella to lean on, and a few surviving mentions in older comments and design
docs do not make one.

## Types and Values

### Color

Color is normalized 0.0–1.0, never 0–255: `Color::Red` is `{1.0F, 0.0F, 0.0F, 1.0F}`. Divide
each channel by 255 when building from 8-bit input such as a hex code or a picker.

Be skeptical of a new hardcoded `RGBA{...}`. Look first for a constant that already says it —
the `Color::` namespace (`Engine/Core/Public/Color/Color.cppm`) holds the standard named colors,
and the editor's `Palette::` holds the UI palette. If nothing matches and the value is reused or
semantically meaningful, add a named constant rather than scattering the literal.

A themable UI element must read the active theme (`m_ActiveTheme->Accent` and siblings, falling
back to `Palette::Accent`), never a literal. A literal on a themable surface silently ignores
the user's theme, which is a bug rather than a style lapse.

### `Label` parameters

Pass `Label` by value — it is a hash, and `const Label&` buys nothing. Iterating or comparing a
container of them (`for (const Label& Name : ...)`) is unaffected; the rule is about parameters.

Convert at API boundaries with `ToCString()` / `ToString()`. When registering into a module's
registries, use that module's wrapper (e.g. `Input::Label`) so the hash carries the module
signature.

### File-format identifiers

An on-disk format's magic number is 8 ASCII characters packed little-endian into a `uint64_t`,
as a 3-letter system prefix plus a 5-letter structure name:

| Identifier | System | Structure |
| --- | --- | --- |
| `CTXSTRAT` | Cortex (`CTX`) | Stratum |
| `MSCLYOUT` | Mosaic (`MSC`) | Layout |

Every one is registered in `IO::File::Identifiers` (`Engine/Core/Public/IO/File.cppm`) through
`ConvertToHex`, which carries a compile-time uniqueness `static_assert`: two modules cannot mint
the same tag, because the second collides at compile time. Never define a module-local magic
constant — an unregistered tag is exactly the collision the table exists to prevent.

## Placement and Reuse

### Helper placement

Before putting a generic-looking helper — a byte buffer, a formatter, an indent tracker, a
string splitter, a scope guard, anything with nothing module-specific about it — inside the
first module that consumes it, ask where it belongs. The default home is `Core` or another
lower-level shared library; module-local placement is right only when the type makes sense
solely in that module's vocabulary.

If you would not guess from the name alone that it was specific to the module, ask before
committing rather than letting the first consumer decide placement by accident.

### Reuse before reimplementation

Don't hand-roll common work at the call site — splitting or trimming text, hashing, byte
packing, clamp/lerp math, ad-hoc linear searches, scratch buffers, path manipulation. Look for a
proven implementation first: `Std`, `Core` (Structures, IO, Identity, …), or the owning module's
existing helpers. If none exists and the need recurs, extract a named helper into the right
shared library (placement per the section above) instead of inlining another copy — one proven
implementation, many call sites. Implementation sites for our own structures should read as
domain logic, not as algorithm plumbing.

### Platform names outside the platform modules

`Docs/StyleGuide.md` §Platform Isolation keeps platform *logic* behind the liaison. The boundary
holds at the level of names as well. A platform name — `Wayland`, `X11`, `Windows`, `Win32`,
`macOS`, `Cocoa`, `POSIX` — in an identifier, type, branch, or include outside
`Engine/Modules/Platform/` is a coupling smell even when the code around it is portable. Shared
modules say *what* they need (a window surface, a clipboard, a file dialog), never *which* OS
provides it.

Prose in genuine platform-liaison documentation, and build or CI configuration that legitimately
selects a backend, are outside the rule.

## Escape Hatches

### pImpl decision gate

Never introduce pImpl (`unique_ptr<Impl>` behind a forward-declared `Impl`) in a new Phoenix
type unless one of these holds:

1. **ABI stability across a dynamic linker boundary**, where consumers do not rebuild when the
   representation changes. This is what pImpl is actually for.
2. **A private type genuinely forbidden in the public TU set** — a header whose macros or OS
   declarations would poison callers.
3. **Runtime strategy or state polymorphism**, where `Impl` will have several concrete
   subclasses chosen at construction.

Header weight is **not** a justification here. The engine rebuilds everything on every change,
and every peer class holds its members by value. Reaching for pImpl to avoid a transitive
include is pattern-matching on an ABI-stable library project, which this is not.

If none of the three applies, either flatten to direct value members (the default), or
forward-declare and `unique_ptr` the one genuinely heavy field without growing it into a full
pImpl. If the work really needs pImpl anyway, say so in the PR description with the
justification so a reviewer can weigh it.

### clang-tidy NOLINT

NOLINT is rare, and every use carries a one-line reason naming why neither a code change nor a
`.clang-tidy` tuning was viable. Work the options in order and stop at the first that applies:

1. **Restructure so the check does not fire.** The default answer.
2. **Tune `.clang-tidy`.** A check firing across the whole codebase is the wrong check for the
   project; its noise belongs in configuration, not in comments scattered through source.
3. **A narrow `// NOLINT(check-name): <one-line reason>`** on the one line, nowhere wider.

Two hard limits on the third. A file-wide `NOLINTBEGIN`/`NOLINTEND` pair is never the answer for
a style-level check — if `readability-convert-member-functions-to-static` or a similar check
fires on every file, that is step 2, not a wrapper around a translation unit. And the
justification is one short line: if it needs a paragraph, the code needs restructuring.

The canonical legitimate case is the `std::byte*` ↔ `char*` I/O boundary, where bridging byte
buffers to string or stream APIs requires `reinterpret_cast`. That check is disabled repo-wide;
any remaining narrow casts go through one of the project's byte/char helpers with a single-line
NOLINT at the helper site.
