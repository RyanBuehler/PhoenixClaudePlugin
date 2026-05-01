# Style Guide

Phoenix follows a consistent formatting, naming, and design strategy to keep the codebase
readable and tooling-friendly. This document is the authoritative source for code style and
design practice; agents and commands reference it before writing or reviewing code.

## General Rules

- Only make cosmetic changes to code you explicitly modify or add.
- Never reformat code unless you're already modifying it. When reformatting, apply the rules
  below.
- Follow the style of surrounding code.

## Formatting

| Rule | Description |
| --- | --- |
| Column width | Limit lines to 120 characters. |
| Indentation | Use tabs configured to a width of four spaces. |
| Brace style | Follow Allman braces (opening brace on its own line). |
| Alignment | Align consecutive assignments and trailing comments when practical. |
| Includes | Sort case-insensitively and group related headers together. |

Blank line after every `}` that closes a scope (function, class, struct, namespace, enum,
control-flow block, lambda body) before the next non-`}` token. Exceptions — no blank line
is required when the next token is:

- Another closing brace of an enclosing scope
- An `else` / `else if` continuation of the just-closed `if`
- A trailing `;` (e.g. closing a struct or lambda definition)

```cpp
// Required:
void DoThing()
{
    if (Condition)
    {
        HandleIt();
    }

    NextStep();
}

// Forbidden (missing blank line between scopes):
void DoThing()
{
    if (Condition)
    {
        HandleIt();
    }
    NextStep();
}
```

## Naming

Naming is documentation. Choose names that make intent obvious without comments. Spell it
out: `DeltaTime` not `dt`, `FieldOfView` not `FOV`. Well-established acronyms that are
longer than their expansion are acceptable (`AABB`, `ID`). If you need a comment to explain
what a variable holds, rename the variable instead. Single-letter names only for loop
counters (`i`, `j`, `k`).

Use `Previous` not `Old` in field and variable names (`previous_label`, `PreviousState`).

| Entity | Style | Notes |
| --- | --- | --- |
| Types and functions | CamelCase | Applies to both public and private members. |
| Member variables | Prefix with `m_`, optionally followed by a type hint, then CamelCase. |
| Global variables | Prefix with `g_`, optionally followed by a type hint, then CamelCase. |
| Static variables (non-member) | Prefix with `s_`, optionally followed by a type hint, then CamelCase. |
| Locals & parameters | Optional type prefix followed by CamelCase; traditional loop counters may remain single-letter. |

### Type prefixes

- `b` – Boolean
- `a` – Atomic
- `p` – Pointer or smart pointer
- `s` – Static variable (when combined with other prefixes)

Prefixes can compose; for instance, a static member pointer would combine the
member (`m_`) and pointer (`p`) prefixes before the descriptive name.

### Pattern references

- Member variables: `^m_(?:[baps]*)[A-Z][A-Za-z0-9]*$`
- Global variables: `^g_(?:[baps]*)[A-Z][A-Za-z0-9]*$`
- Static variables: `^s_[bap]*[A-Z][A-Za-z0-9]*$`
- Locals/parameters: `^(?:[baps]+)?[A-Z][A-Za-z0-9]*$`

## Language Features

### Exceptions

Forbidden. The keywords `try`, `catch`, `throw`, and `noexcept` do not appear in Phoenix
source. Use `std::expected`, `std::optional`, or result types instead.

### RTTI

Disabled. Do not use `dynamic_cast`, `typeid`, or `reinterpret_cast`. For type-discriminated
queries, use virtual query methods and `From<T>().ID()`.

### `[[deprecated]]`

Forbidden. Do not use deprecated attributes or mark code as deprecated — remove the code
instead.

### `auto`

Do not use `auto` for variable declarations. Spell out the actual type so reviewers see the
contract at a glance.

The only acceptable exceptions are types a human cannot reasonably write out:

- Iterator types (`Container::const_iterator` is fine if you prefer it, but `auto` is allowed)
- Lambda types
- Deeply nested template instantiations where the spelled-out type harms readability

This rule is **especially strict for error-bearing types**. The following must always be
declared with the full type, never `auto`, so the obligation to check the result is visible
at the declaration site:

- `std::expected<T, E>`
- `std::optional<T>`
- Status / result enums and any other type whose unhappy path the caller must handle

```cpp
// Required:
std::expected<Texture, LoadError> Result = LoadTexture(Path);
std::optional<Entity> Found = Registry.Find(Id);

// Forbidden:
auto Result = LoadTexture(Path);
auto Found = Registry.Find(Id);
```

### `const` correctness

Apply by default: `const` local variables, `const` reference parameters, `const` member
functions for accessors.

### `Move` / `Forward`

Use the project's `Move()` and `Forward()` helpers (exported from the `Phoenix` C++20
module) instead of `std::move` and `std::forward`. The wrappers add a `[[nodiscard]]`
return and a `const`-rejection `static_assert` that catches miscasts the standard helpers
allow through. A grep for `std::move` or `std::forward` in Phoenix source should return
zero hits.

### `std::memory_order`

For every use of `std::memory_order`, add a nearby comment explaining why that ordering is
required. This is the canonical example of a non-obvious *why* that belongs in a comment.

## Code Organization

### Namespaces

Namespaces mirror the directory tree. Every segment names a domain or capability —
never a generic bucket. Before introducing a new namespace, grep the codebase to
confirm the name does not collide with an existing class, struct, or namespace at
the same scope.

Anonymous namespaces are forbidden — they break our unity builds. Always name every
namespace.

Directory depth equals namespace depth. Each level of the directory tree adds a
segment:

| Location | Namespace |
| --- | --- |
| `Modules/Rendering/Mosaic/Source/Public/Tile.h` | `Rendering::Mosaic` |
| `Modules/Rendering/Mosaic/Source/Public/Layout/Sorting.h` | `Rendering::Mosaic::Layout::Sorting` |
| `Modules/Audio/Sonic/Source/Public/Voice.h` | `Audio::Sonic` |
| `Modules/Json/Source/Public/Parser.h` | `Json` |
| `Core/Image/PNG/Deflate.h` | `Core::Image::PNG::Deflate` |
| `Applications/Crucible/Source/Server.h` | `Crucible` |

Engine modules nest under their category. Multi-module categories (`Rendering`,
`Input`, `Audio`, `Platform`) group their modules as `<Category>::<Module>` — for
example `Rendering::Mosaic`, `Input::Conduit`. Single-module categories stay flat
(`Json`, `Ledger`, `Dispatch`, `Script`). Inside a module namespace, no class or
struct may share the module segment's name; `class Mosaic` inside `namespace
Rendering::Mosaic` is forbidden — pick a name that describes the type's role.

The IModule integration class for a module follows a uniform suffix: module
`<Module>` exposes `class <Module>Module` and that class lives at **global scope**,
not inside the module namespace. Examples: `VigilModule`, `SpatialModule`,
`SoulforgeModule`, `ArbiterModule`, `ArchiveModule`, `EngineModule`. The module
namespace (`namespace Vigil`, `namespace Soulforge`, etc.) holds support types —
components, helpers, internal data structures — never the integration class
itself. This sidesteps the class/namespace name collision and keeps the module
class visible to consumers under one consistent path (`shared_ptr<EngineModule>`,
`IEngineSubsystem<EngineModule>`, `Subsystem::Metadata<EngineModule>`).

Applications use their brand name as a flat top-level namespace: `namespace
Crucible`, `namespace Vigil`, `namespace Editor`, `namespace Forge`, `namespace
Game`, `namespace Minimal`. Do not wrap apps in an `Application::` parent and do
not use a generic `namespace Application` — it carries no information and is
indistinguishable across binaries in logs and stack traces.

Log channels live in flat top-level namespaces named `<Module>Log`: `EngineLog`,
`RealmLog`, `DispatchLog`, `ArbiterLog`, `ScribeLog`, etc. Each lives in
`<Module>Log.h` next to its module sources and pulls in the shared
`Logging/Log.inl` template for the `Trace` / `Log` / `Warn` / `Error` / `Fatal`
API. Source files acquire their channel with a file-scope `using namespace
ArbiterLog;` (or similar) after the includes. The eventual target is to nest log
channels under their owning module as `::Log` (`Rendering::Mosaic::Log`,
`Ledger::Log`), but until a cross-codebase migration converts every channel at
once, individual modules must not flip independently — that yields a half-and-half
codebase where readers cannot predict the spelling. Stay flat until the migration
ships.

The following namespace segment names are forbidden — they describe nothing about
what the code does:

- `Detail`
- `Internal`
- `Helpers`
- `Utils`
- `Misc`
- `Common`

Replace them with a name that describes the contents. `UI::Helpers` might split
into `UI::HitTest` and `UI::ClipRect`. `Trials::Helpers` becomes
`Trials::Assertions`. `Dispatch::Tools` stays (it names a real domain). When in
doubt, ask: *what do these symbols do?* — that's the namespace name.

### `using namespace`

Scoped `using namespace` directives shorten call sites without hiding the
underlying type names. They are forbidden in headers (`.h`, `.hpp`, `.ixx`, and
any header-like file), because the directive leaks into every translation unit
that includes the header.

At file scope in a `.cpp` file they are allowed, and this is the idiomatic way
to pull in a log channel for the whole translation unit (e.g. `using namespace
Ledger::Log;` at the top of `Ledger.cpp`, placed after the includes and before
any definitions).

Inside a function body, use `using namespace` only when the namespace is
referenced twice or more. For a single reference, fully-qualify — the `using`
buys nothing.

### Platform Isolation

Keep platform-specific logic (for example, Linux-only behavior) confined to the corresponding
platform liaison sources so code for other platforms remains encapsulated and unaffected.
Files under `Modules/Platform/` are exempt from the platform-API ban.

## Error Handling

Do not silence return values that callers are expected to consume. Forbidden patterns include
`(void) Foo();`, `[[maybe_unused]] auto _ = Foo();`, and `std::ignore = Foo();` when `Foo`
returns an error-bearing type (`std::expected`, `std::optional`, status enums, etc.). Inspect
the result and, on the unexpected branch, log via `Scribe` at the appropriate severity
(`Warning` for recoverable conditions, `Error` for ones that compromise correctness).

`expected<T, E>` functions must use the error channel on bad input; never return a
default-constructed `T` as a silent failure.

## Comments

Code should read as self-documenting. Reach for a comment only when the *why* is not obvious
from the code itself, or when a reader needs a nudge past something complex. A comment is a
small aid, not a technical write-up.

- **Default to no comment.** Add one only when it tells a future reader something the code
  cannot.
- **Short.** Most comments are a single line. Two or three lines is the ceiling — if it needs
  more, the explanation belongs in the commit message, PR description, or a design note, not
  the source.
- **Explain *why*, not *what*.** Never restate what the code does. `// increment counter`
  above `++counter;` is noise.
- **Nothing that can go stale.** No file paths, no line numbers, no symbol names from
  elsewhere, no Crucible labels, no PR numbers, no branch names, no commit hashes, no dates,
  no author tags. If a reader should "see also" something, the reader can grep.
- **No temporal narration.** Forbidden words in comments include "previously", "now", "new",
  "legacy", "refactored", "was", "used to". Future readers see only the current code;
  commentary about what *used* to be there is noise. Decisions about why code changed belong
  in the commit message and PR description.
- **No decorative banners.** Section headers like `// ===== Helpers =====` or ASCII rules
  are forbidden. Use scope and naming instead.
- **No author, date, or ticket tags inside comments.** `git blame` is authoritative.
- **Form.** Use `//` for single-line comments. For multi-line comments, use `/* ... */`.
  Do not stack multiple `//` lines to form a paragraph.
- **Placement.** Prefer a comment on its own line directly above the code it explains.
  Trailing end-of-line comments are reserved for brief annotations (labeling an `else` whose
  `if` is far above, tagging a `switch` case, etc.) and must stay short.
- **Public API declarations require a comment.** Every exported class, struct, free function,
  and public member function declared in a module's public header gets at least a single-line
  comment describing its purpose. Prefer one line; use the multi-line `/* ... */` form only
  when a single line genuinely cannot convey the contract.

The `std::memory_order` comment rule is a canonical example of a non-obvious *why* that
belongs in a comment.

## TODO Comments

TODOs in code are notes to a future programmer who has none of today's context. Write them
so they stay useful as the codebase moves around them.

- **Keep them short.** One line, one sentence. If a TODO needs a paragraph, the work needs a
  Crucible challenge or bug, not a comment.
- **Describe the work, not the origin.** State what needs to happen, not where the note came
  from.
- **No parenthesized prefix.** Write `// TODO: ...`, never `// TODO(anything): ...`. The
  `TODO(label):` form is forbidden regardless of what the label is — Crucible labels, saga
  names, PR numbers, owner handles, ticket IDs, dates, and file-path shorthand all belong
  somewhere else (commit message, PR description, tracker). A grep for `TODO(` in source
  files should return zero hits.
- **Never reference anything that can go stale.** No file paths, no line numbers, no Crucible
  labels, no PR numbers, no branch names, no commit hashes, no agent names, no date. All of
  those drift the moment something is renamed, rebased, squashed, archived, or merged. The
  TODO should still make sense a year later when none of that context exists.
- **Do not annotate work you just did.** TODOs that explain a refactor, justify a recent
  rename, or narrate a decision belong in the commit message and PR description — not the
  source. Future readers see only the current code; commentary about what *used* to be there
  is noise.
- **Do not annotate trivially obvious follow-ups.** "TODO: also update the header" is
  something you do now, not later.

Good:

    // TODO: handle UTF-8 surrogate pairs in token splitter

Bad:

    // TODO(execute-saga-canvas-overhaul): per code review on PR #312, see Modules/Mosaic/Canvas.cpp:142
    // TODO: previously this used a raw pointer, switched to CanvasLease in this commit
    // TODO: address feedback from challenge `add-viewport-resize`

## Design Practices

### 1. Ownership & Pointers

`new`/`delete` are banned. Use `std::unique_ptr` for exclusive ownership, `std::shared_ptr`
for shared ownership, or engine handle types. Non-owning raw pointers are acceptable when
nullability or reseatability is required and the lifetime is guaranteed by the caller. Prefer
references (`T&`) when the relationship is always-valid and never-changes.

### 2. Singletons

Avoid. Prefer the subsystem pattern: a module registers an abstract interface
(`Subsystem::RegisterInterface<IFoo>(...)`) that exposes only what consumers need. Consumers
access it via `Subsystem::Get<IFoo>()`, which returns a validated reference that must be
checked before use. This provides decoupling, controlled lifecycle, and testability. If a
singleton is unavoidable, it must be thread-safe, its lifetime must be explicit, and the
justification must be documented.

### 3. Macros

Prohibited except where no C++23 alternative exists (e.g., test registration, third-party C
API interop). Use `constexpr`, `consteval`, concepts, or templates instead. Any new macro
must document why a compile-time construct is insufficient.

### 4. Preprocessor Guards

`#ifdef`/`#if` are prohibited in shared code. Build configuration is provided as `constexpr`
values generated by CMake (see `Build::IsDebugBuild`, `Build::IsProfilingEnabled`). Use
`if constexpr` for configuration branching — the dead branch is eliminated at compile time
but still type-checked, catching refactoring errors. Platform-specific behavior lives in
platform modules. Rendering API interop (Vulkan) may use `#ifdef` in its own module with
justification.

### 5. Lint Bypass

`// NOLINT`, `// clang-format off`, and similar directives are prohibited unless the
alternative is worse (e.g., C API callbacks with fixed signatures). Must include an
explanatory comment. Fix the code, don't suppress the warning.

### 6. Labels Over Strings

For identity comparisons (actions, signals, categories), use `Label` types with compile-time
FNV-1a hashing instead of raw string comparisons. Integer comparisons are constant-time and
cache-friendly. Define constants as `inline constexpr Label`. See `Impulse/Signal/Label.h`.

For tooling mechanics — formatter configuration, linter layers, command invocations, and
troubleshooting — see `references/tooling.md`.
