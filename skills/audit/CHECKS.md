# Audit — Check Catalog

Each check has a stable greppable ID, a severity, a fix tier, the repository section that owns
the rule, a detection heuristic, and a fix direction. Apply every check in scope to each
in-scope file.

**This catalog holds no rules of its own.** Every check names the document section that owns its
rule, and that section is the source of truth. If a check and its **Rule** disagree, the rule
wins and the fix belongs here. A recurring violation with no owning section is not a check yet —
strengthen `Docs/StyleGuide.md` or the repository's `CLAUDE.md` first.

## Severity rubric

- **Critical** — runtime/correctness risk (use-after-free shape, swallowed error, architecture
  contract violation reaching across a module boundary, forbidden keyword that silently changes
  semantics)
- **Warning** — tech debt, convention violation without runtime risk, maintainability smell
- **Nit** — style consistency, documentation polish

If in doubt between Warning and Nit, choose Warning. Audit's value is catching drift; being
permissive defeats the purpose.

## Fix tiers

Severity says how much it matters. The tier says what you may do about it.

- **mechanical** — a single-line replacement with no judgment in it. Apply it.
- **judgment** — several defensible answers exist, or the change crosses a signature. Ask, one
  question at a time, and apply the answer. Never sweep a tree of these: a word-boundary regex
  cannot tell one of our identifiers from the same word in a sentence.
- **report** — a cross-file refactor. Report it and name the follow-up; do not attempt it.

Three checks carry **Requires approval**: `reference-member`, `global-singleton`, and
`trailing-preposition`. New code may not introduce the shape without Ryan's sign-off, and an
existing one is never touched under `--fix-safe` — it goes to the report with the approval
requirement stated, so a rotation cannot quietly authorize one.

## Running one group

Each lettered group is a unit a focused audit can run on its own
(`/phoe:audit --checks=naming`). A group's checks share a theme, not a language feature,
because a theme is what a focused report needs to stay short enough to act on.

---

## A. Naming

### `noun-as-function-name` (Warning, judgment)
A function named with a bare noun — `Snapshot()`, `Count()`, `Config()`, `Node()`. The name says
what comes back and never what the call does, so a reader cannot tell whether it hands back held
state or builds a new value on the spot, and therefore cannot tell whether calling it twice is
free.

**Rule**: `Docs/StyleGuide.md` §Accessor naming.

**Detection**: a member or free function whose name is a noun with no verb, especially one whose
doc comment opens "Return the …" — the comment is carrying the verb the name dropped. Also flag
a name that collides with a type of the same spelling in scope.

**Fix**: decide which it is. A call handing back owned state is an accessor and carries `Get`
(`GetSnapshot`). A call that performs work takes the verb for that work (`BuildSnapshot`).

### `bare-noun-accessor` (Warning, judgment)
A value-returning accessor spelled as a bare noun — `Size()`, `Count()`, `Name()` — where the
prefixed form is the rule.

**Rule**: `Docs/StyleGuide.md` §Accessor naming.

**Detection**: a `const` member returning a value, named without `Get`. The bare form still
outnumbers the prefixed one across the tree; that is drift, not the rule, so prevalence argues
the wrong way here.

**Fix**: rename to `GetX` as you touch the declaration, never in a tree-wide sweep. Do not
"correct" a prefixed accessor back to the bare noun because its neighbors use one.

### `trailing-preposition` (Warning, judgment) — **Requires approval**
A function name ending in a preposition — `NodeAt`, `ConfigFor`, `LoadFrom`, `ScrollBy`,
`AppendTo`, `IsValidIn`. The name starts a sentence the parameter list has to finish. The
dangling case is worst: `IsValidIn(Thing, bIsRoot)` leaves "valid in *what*?" open, because a
boolean describing a place is not the place.

**Rule**: `Docs/StyleGuide.md` §No trailing prepositions.

**Detection**: an identifier ending `At`/`For`/`From`/`To`/`By`/`In`/`On`/`With`/`Into`. Expect
false positives — `Into`, `From` and `To` are ordinary English as well as house vocabulary.

**Fix**: name the thing the call answers with and let the parameters say what it acts on —
`GetNode(Index)`, `Load(Path)`. A new name follows the rule from the day it is written and needs
no approval; **renaming an existing one is approved individually, never in a batch.** The tree
carries 200-odd across some 2,400 call sites. A previous regex sweep of this shape rewrote prose,
renamed parameters into a shadowing bug, and ate the parameter list off 34 signatures across 5
files. Enumerate exact identifiers into a map first, then rename from the map.

### `decorated-verb-variant` (Warning, judgment)
A new name coined for an operation the tree already names — `BakeInto` added alongside the
`Record` it delegates to. The preposition may have a perfectly good object; the harm is the fork.
One operation with two spellings makes a caller one level up performing the same verb read as
doing something else.

**Rule**: `Docs/StyleGuide.md` §No trailing prepositions, final subsection.

**Detection**: a new method that immediately delegates to one method on another object. Grep the
bare verb; if it already exists, this is a variant.

**Fix**: use the name already there.

### `manager-name` (Warning, judgment)
A type or variable named `*Manager`, or its abbreviations `Mgr` and `DM`. "Manager" describes no
responsibility.

**Rule**: `Docs/StyleGuide.md` §`*Manager` is not a name.

**Detection**: `Manager` in a type, member, parameter, or local name. Two spellings are exempt
because the word is not ours to choose: a name mirroring an OS or protocol object
(`xdg_toplevel_icon_manager_v1`, `m_pDataDeviceManager`), and the real-world sense as in an OS
package manager.

**Fix**: name the type for what it *owns* — `ThemeCatalog`, `DockSpace`, `FocusTracker` — or as a
`*Subsystem` where foreign code reaches it through the registry. A variable inherits the rule
from the type it holds.

### `lopped-abbreviation` (Warning, mechanical in one file / judgment across a header)
A name shortened by dropping vowels or syllables — `Ctx`, `Req`, `Fmt`, `Msg`, `Buf`, `Tmp`,
`Cfg`, `Idx`, `Ptr`, `Sz`, `Len`, `Cnt`.

**Rule**: `Docs/StyleGuide.md` §Naming — the forbidden-form table.

**Detection**: the table's entries on a word boundary. The table is not exhaustive; the general
rule takes precedence over it, so flag an unlisted short form that reads as a lopped word.

**Fix**: write the full word. If you paused to decide whether to abbreviate, the answer is the
long form.

### `restated-container-prefix` (Warning, judgment)
A member repeating its enclosing type — `Commands::RunCommand`, `Handlers::DispatchHandler`.

**Rule**: `Docs/StyleGuide.md` §Method Naming Inside Containers.

**Detection**: a member name containing the singular of its enclosing type's name. The rule is
about redundancy, not the noun — `Commands::BuildCommandLine` is fine, because a `CommandLine` is
a different thing from the enclosing scope.

**Fix**: let the verb stand alone.

### `detail-namespace` (Warning, judgment)
`namespace Detail` — or `Details`, `Internal`, `Impl`, `Private`. The name marks the contents
off-limits instead of saying what they do, so a reader looking for the behavior has no word to
grep for.

**Rule**: `Docs/StyleGuide.md` §Namespaces.

**Detection**: those five spellings after `namespace`.

**Fix**: a domain-scoped name for the work — `LabelValidation`, `JsonCoercion`,
`Path::Resolution`. If no verb-oriented name suggests itself, the code probably belongs on an
existing type rather than in a free-function scope.

### `anonymous-namespace` (Warning, judgment)
An unnamed namespace, or one named emptily or generically.

**Rule**: `Docs/StyleGuide.md` §Namespaces. Anonymous namespaces break our unity builds.

**Detection**: `namespace {` or a namespace named `Helpers`/`Util`/`Misc` at file scope.

**Fix**: name it for what the contents do. For UI/Mosaic helpers prefer an existing scope such as
`UI::Helpers`. Grep before introducing a new namespace name to confirm it does not collide with a
class, struct, or namespace at the same scope.

### `bare-flow-noun` (Warning, judgment)
A type or member named exactly `Sink`, `Source`, or `Drain`, unqualified. The bare noun names a
direction of flow and nothing else.

**Rule**: the repository's `CLAUDE.md` §Structure & naming.

**Detection**: those three as a whole identifier. Qualified forms are correct and common —
`ShaderSource`, `TrialBatchSource`, `ILocusSource` — as is `drain` the verb.

**Fix**: qualify it with what it holds or does.

### `temporal-name` (Warning, judgment)
`Old*` where `Previous*` is meant, `Last` for the one before this one, `Maybe*` for `Tentative*`,
`Kind`/`*Kind` for `Type`/`*Type`.

**Rule**: the repository's `CLAUDE.md` §Code style; `Docs/Lexicon.md` §Last, §Kind.

**Detection**: those prefixes and suffixes. `Last` also means *final in a sequence*, and that
meaning stays — the last element, `First`/`Last`, "declared last" — so read the referent before
flagging.

**Fix**: the blessed word. Scoped to one declaration and its references in the same file, this is
mechanical; across a header it is judgment.

### `single-letter-name` (Nit, judgment)
A single-letter identifier outside a loop counter.

**Rule**: `Docs/StyleGuide.md` §Naming.

**Detection**: a one-character declaration that is not `i`, `j`, `k` in a `for`.

**Fix**: spell out what it holds.

### `wrong-type-prefix` (Warning, mechanical)
A member, global, or static missing its `m_`/`g_`/`s_` prefix, or a bool/atomic/pointer missing
its `b`/`a`/`p` type hint.

**Rule**: `Docs/StyleGuide.md` §Type prefixes, §Pattern references.

**Detection**: the four regexes in §Pattern references.

**Fix**: apply the prefix.

### `mixed-case-acronym` (Nit, mechanical)
An acronym in mixed case in a module or type name — `Gltf` for `GLTF`.

**Rule**: the repository's `CLAUDE.md` §Code style. `Json` is the lone exception.

**Detection**: a known acronym in CamelCase.

**Fix**: all-caps it.

### `subdirectory-restated-in-filename` (Nit, mechanical)
A public header restating its own subdirectory in its filename.

**Rule**: `Docs/StyleGuide.md` §Module Source Layout — the subdirectory already supplies the
qualifier at the include site.

**Detection**: a filename under `Source/Public/<Dir>/` beginning with `<Dir>`.

**Fix**: drop the prefix from the filename.

---

## B. Ownership and lifetime

### `reference-member` (Warning, judgment) — **Requires approval**
A data member declared as a reference — `RealmModule& m_Directory`, `Service& m_Service`. A
lifetime contract written in a punctuation mark: nothing at the declaration says who guarantees
the referent outlives the holder, so the rule lives in whichever constructor happens to be
correct today. It cannot be reseated, and it silently deletes the type's copy-assignment
operator — so the class stops working in a `vector`, in a `sort`, or behind any code that
assigns, and the error surfaces at the container rather than at the member. It cannot be null,
which reads like a safety guarantee, but a dangling reference is not a checkable state.

**Rule**: `Docs/StyleGuide.md` §Ownership & Pointers; the repository's `CLAUDE.md` §Structure &
naming.

**Detection**: an `&` between a type and an `m_` name at class scope. Roughly four dozen exist
today and are debt, not precedent — one sitting next to a change is not a licence to add another.

**Fix**: a non-owning raw pointer where the lifetime is the caller's to guarantee (it reseats, it
leaves the type assignable, and `if (!m_Directory)` is a check the class can make); the `Lease`
the registry hands back where the referent is a system; or a `shared_ptr<const T>` snapshot where
the value is small and shared immutably. State the ordering the class depends on but does not
control, at the member. **New instances need Ryan's sign-off, justified in the PR description.**

### `global-singleton` (Critical, report) — **Requires approval**
A private constructor paired with a `static T& Get()` or `static T& Instance()`, or any free
function handing back the one instance of something. Every consumer's dependency becomes
invisible at its declaration, nothing can be constructed in a test without standing up the global
first, and the lifetime is whatever the linker decided.

**Rule**: `Docs/StyleGuide.md` §Singletons; the repository's `CLAUDE.md` §Structure & naming,
which is stricter and binds — no new global singletons and no static `Get()` accessors at all.

**Detection**: `static <T>& Get()` / `Instance()` on a type with a private or deleted
constructor. A handful predate the rule; the §Singletons exception covers those, not something
new.

**Fix**: `Docs/Patterns.md` §Registry Mediation — the owner publishes a narrow Tier-2 interface
into the subsystem registry, and consumers resolve it by identity and check the result before
use. Where a consumer needs a capability rather than a system, an owner-injected closure.
**A new one needs sign-off before it is written, not after it is reviewed.**

### `self-subscribing-constructor` (Critical, report)
A constructor resolves a subsystem it is not, finds a graph or manager, and enrolls `this`; the
destructor unenrolls. The object can no longer exist without the engine standing up around it, so
the cheapest test of its own logic needs a live registry, a graph, and a driver. The constructor
also has nowhere to put a refusal — it logs, and a log line is not something a caller or a trial
can act on.

**Rule**: `Docs/Patterns.md` §Self-Subscribing Constructor.

**Detection**: `Subsystem::Acquire<...>` inside a constructor, usually paired with a
`bool m_bSubscribed` and a logged error on the failure path.

**Fix**: `Docs/Patterns.md` §Scoped Subscription — keep the participant inert and let a scope
object hold the enrollment, so the refusal is a value the caller can read.

### `pull-mutate-push-accessor` (Critical, report)
A `Get*()` hands back a pointer or reference to something the callee owns; the caller mutates it
across a stretch of code, then passes it back to a second call that consumes it. The owner's
invariants are now enforced by every caller, one copy each.

**Rule**: `Docs/Patterns.md` §Pull-Mutate-Push Accessor.

**Detection**: the round trip — the same object leaves through one call and returns through
another.

**Fix**: `Docs/Patterns.md` §Submitted Request — describe the work, let the owner realize it,
read the result. Where the accessor only reads and the owner replaces its value rather than
mutating it, a `shared_ptr<const T>` snapshot resolves it instead.

### `public-accessor-to-owned-internal` (Warning, report)
A public accessor returning a reference to an owned internal, short of the full round trip above.

**Rule**: the repository's `CLAUDE.md` §System access — ownership tiers.

**Detection**: a public method returning `T&` or `T*` to a member.

**Fix**: expose the operation, not the object.

### `raw-new-delete` (Critical, report)
`new` or `delete` in engine or application source.

**Rule**: `Docs/StyleGuide.md` §Ownership & Pointers.

**Detection**: the bare keywords, excluding placement forms in an allocator.

**Fix**: `unique_ptr` for exclusive ownership, `shared_ptr` for shared, or an engine handle type.

### `reflexive-pimpl` (Warning, report)
A new type with a `unique_ptr<Impl>` behind a forward-declared `Impl`, introduced to keep an
include out of a header. The engine rebuilds everything on every change, so the compile-time
argument buys nothing, and the indirection costs an allocation, a pointer chase, and a second
place every member has to be found.

**Rule**: `Docs/StyleGuide.md` §pImpl.

**Detection**: a `unique_ptr<Impl>` member with `Impl` forward-declared and defined in the `.cpp`.
Three justifications survive — ABI stability across a dynamic linker boundary, a private type
genuinely forbidden in the public TU set, and runtime strategy polymorphism.

**Fix**: flat value members. Where one field is genuinely heavy, forward-declare and `unique_ptr`
that field alone. If pImpl is right anyway, say so in the PR description.

---

## C. Errors and control flow

### `void-cast-discard` (Critical, judgment)
`(void) Foo();` — and `std::ignore = Foo();`, `[[maybe_unused]] auto _ = Foo();` — over a call
returning something a caller is expected to consume. The cast is not a decision, it is the
silencing of one: `[[nodiscard]]` fired because the callee's author decided its result must be
handled, and the cast overrules that from the call site, where the least context exists.

**Rule**: `Docs/StyleGuide.md` §Error Handling; the repository's `CLAUDE.md` §Code style.

**Detection**: the three spellings over an error-bearing return (`expected`, `optional`, a status
enum). Trials carry most of the tree's remaining discards; production source should return none.

**Fix**: inspect the result and log the unexpected branch through `Scribe` — `Warning` for a
recoverable condition, `Error` for one that compromises correctness. If the result genuinely does
not matter to any caller, the annotation is wrong rather than the call site: drop the
`[[nodiscard]]`, or restructure so the call returns nothing.

### `try-prefixed-call` (Warning, judgment)
A function named `Try*` — `TryLoad`, `TryParse`, `TryRegister` — usually returning a bare `bool`.
We do not try in Phoenix; we execute. `Try` plus `bool` collapses three outcomes into one bit and
discards the reason for all of them, so the caller cannot tell "it declined, which is normal"
from "the input was malformed".

**Rule**: `Docs/Patterns.md` §Try-Prefixed Call.

**Detection**: the `Try` prefix, and more broadly any call answering "did it work" with one bit
where three outcomes exist.

**Fix**: name the function for the operation, imperatively, and return `expected<T, string>`
where there is room for an error. Keep the outcomes distinct: a value is success, an error is a
fault, a legitimate absence is `optional<T>` — never an error. Where all three occur,
`expected<optional<T>, string>` states exactly that.

### `default-constructed-silent-failure` (Critical, judgment)
An `expected<T, E>` function returning a value-initialized `T` on bad input rather than taking
the error channel. The caller's `if (Result)` passes and the empty `T` travels on, surfacing
wherever it is first indexed or trusted.

**Rule**: `Docs/StyleGuide.md` §Error Handling.

**Detection**: `return {};` or `return T{};` on a validation branch of an `expected`-returning
function.

**Fix**: return the error, with a sentence naming what was wrong with the input.

### `exception-keyword` (Critical, report)
`try`, `catch`, or `throw`, or `noexcept` used as an exception-safety annotation.

**Rule**: `Docs/StyleGuide.md` §Exceptions. Language-mandated forms stay — a coroutine's
`final_suspend()` and `std::hash` specializations must be `noexcept` to compile.

**Detection**: the keywords outside those mandated forms.

**Fix**: `std::expected`, `std::optional`, or a result type.

### `auto-on-error-bearing-type` (Warning, judgment)
`auto` on a variable, and especially on an `expected`/`optional`/status return, which hides the
obligation to check the result at the declaration site.

**Rule**: `Docs/StyleGuide.md` §`auto`.

**Detection**: `auto` declarations. Exempt: iterator types, lambda types, and deeply nested
template instantiations a human cannot reasonably write out.

**Fix**: spell the type.

---

## D. Language features and types

### `rtti-cast` (Critical, report)
`dynamic_cast`, `typeid`, or `reinterpret_cast`. RTTI is disabled.

**Rule**: `Docs/StyleGuide.md` §RTTI.

**Fix**: virtual query methods and `From<T>().ID()`.

### `static-cast-proliferation` (Warning, report)
Three or more `static_cast`s in one function or file — a type-design smell, not a per-cast
finding. One side of the conversion is the wrong type.

**Rule**: `Docs/StyleGuide.md` §`static_cast` proliferation.

**Detection**: count per function and per file. One cast at an API boundary is fine; the signal
is the proliferation.

**Fix**: reshape the types — tighten the source, add a wrapper or `enum class`, or move the
conversion to a single boundary. Report it; do not delete casts.

### `std-move-instead-of-Move` (Warning, mechanical)
`std::move` or `std::forward` where `Move` / `Forward` (from `Std`) is the rule. Ours add a
`[[nodiscard]]` return and a `const`-rejecting `static_assert`, and the `std::` spellings resolve
unreliably across module boundaries.

**Rule**: `Docs/StyleGuide.md` §`Move` / `Forward`.

**Detection**: a grep for the `std::` forms should return zero hits in shared source.

**Fix**: swap the spelling.

### `filesystem-outside-the-seam` (Critical, report)
A `<filesystem>` include or `std::filesystem::*` use outside `Engine/Core/{Public,Private}/IO/`,
including the bare `filesystem::` spelling and an `fs::` alias.

**Rule**: `Docs/StyleGuide.md` §Filesystem. `Tools/audit_io_seam.py` fails over it.

**Detection**: the three spellings. Exempt: the wrapper's own implementation, and platform code
where an OS API demands a `std::filesystem::path` shape — the ban targets the operations, not the
path type at an unavoidable boundary.

**Fix**: `IO::File` / `IO::Directory` / `IO::Path`. If the wrapper lacks the operation, say so —
the fix is to extend `IO::*`, not to bypass it at the call site.

### `deprecated-attribute` (Warning, report)
`[[deprecated]]`, or any deprecation path. This is unreleased software.

**Rule**: `Docs/StyleGuide.md` §`[[deprecated]]`.

**Fix**: remove the code.

### `trailing-return-type` (Nit, mechanical)
`auto F(...) -> T` where the return does not depend on the parameters.

**Rule**: `Docs/StyleGuide.md` §Return type syntax.

**Fix**: write the return type first. Trailing syntax is reserved for a return deduced through
`decltype`.

### `incomplete-special-members` (Warning, mechanical)
One of the five special members declared without the other four — including a lone
`~T() = default;`.

**Rule**: `Docs/StyleGuide.md` §Special member functions.
`cppcoreguidelines-special-member-functions` runs as a hard error with `AllowSoleDefaultDtor`
left at `false`.

**Fix**: declare all five, defaulting or deleting each to state the type's intent.

### `magic-number` (Warning, judgment)
A bare numeric literal other than `0`, `1`, `-1` in an expression.

**Rule**: `Docs/StyleGuide.md` §Magic numbers. `cppcoreguidelines-avoid-magic-numbers` is a hard
error.

**Detection**: literals in expressions. A literal that *initializes* a `const`/`constexpr`
definition is itself the named constant and is exempt, so literals inside a
`static constexpr` aggregate initializer do not count.

**Fix**: name the constant.

### `unexplained-memory-order` (Warning, judgment)
`std::memory_order` with no nearby comment saying why that ordering is required. The canonical
example of a non-obvious *why* that belongs in a comment.

**Rule**: `Docs/StyleGuide.md` §`std::memory_order`.

**Fix**: add the sentence.

### `nullptr-comparison` (Nit, mechanical)
A pointer or handle compared against `nullptr` rather than tested directly.

**Rule**: the repository's `CLAUDE.md` §Code style.

**Detection**: `!= nullptr` / `== nullptr`. Audit your own added lines; do not churn pre-existing
comparisons.

**Fix**: `if (!Current)`, `REQUIRES(Found, ...)`.

### `std-isfinite` (Nit, mechanical)
`std::isfinite` where `Math::IsFinite` is the rule — it constant-evaluates and needs no `<cmath>`,
which the curated `Std` does not carry on the clang arm.

**Rule**: the repository's `CLAUDE.md` §Code style.

**Fix**: swap the spelling.

### `unguarded-float-clamp` (Warning, judgment)
A clamp, `min`, `max`, or narrowing cast over a caller-supplied float with no finite guard. A
bare clamp is NaN-transparent — every ordered comparison with NaN is false — so a NaN or Inf
flows straight through and a later narrowing cast or device setter is undefined.

**Rule**: `Docs/StyleGuide.md` §Defensive Coding.

**Fix**: `Math::FiniteClamp`, or `Math::Saturate` for the `[0, 1]` case.

### `unbounded-allocation-count` (Critical, judgment)
A count read from untrusted bytes feeding a `reserve`, `resize`, or `Count * sizeof(Element)`
product without being capped against the remaining payload first. The multiply itself can
overflow, and an inflated count drives a `bad_alloc` into `std::terminate` under
`-fno-exceptions`.

**Rule**: `Docs/StyleGuide.md` §Defensive Coding.

**Fix**: `Parcel::BoundedCount`, which divides rather than multiplies; then read elements
incrementally.

### `unvalidated-image-data` (Critical, judgment)
Indexing an `Image::Data` without `HasSufficientPixels()`. A `Data` whose `Pixels` is smaller than
`Width * Height * BytesPerPixel()` turns every pixel offset into a buffer overrun.

**Rule**: `Docs/StyleGuide.md` §Defensive Coding.

**Fix**: call the guard before any indexing path.

### `out-parameter` (Warning, judgment)
A caller-provided reference to fill where a returned `optional<T>` / `expected<T, E>` would do.

**Rule**: `Docs/StyleGuide.md` §Out parameters.

**Detection**: a non-const reference parameter that the function only writes. The bar for keeping
one is an allocation that shows up in a profile on a per-frame or per-sample path; "I expect this
to be called a lot" is not the bar. `consteval` parsers keep theirs — they run at compile time,
so there is no allocation to avoid.

**Fix**: return the value. Where the operation *is* collection into the caller's container, the
verb is `Gather`. Out-parameters carry the `Out` prefix; byte buffers are `vector<byte>` /
`span<const byte>`, never `uint8_t`.

---

## E. Architecture

### `cross-module-object-handoff` (Critical, report)
A concrete module type (`FooModule&`, `FooModule*`, `shared_ptr<FooModule>`) as a parameter
outside `FooModule`'s own files.

**Rule**: the repository's `CLAUDE.md` §System access — ownership tiers.

**Fix**: route through the Tier-2 subsystem interface, which names no concrete type.

### `self-registering-component` (Critical, report)
A component handing a system a reference to itself — concrete or interface — so it can register
callbacks or be "made ready". If an owner hands a foreigner a capability the foreigner then calls
back into, the dependency is inverted.

**Rule**: the repository's `CLAUDE.md` §Boundary data flow.

**Fix**: submit a self-contained description of the work; pass values, not closures over foreign
mutable state. Prefer a declarative per-tick snapshot the owner consumes.

### `void-star-in-public-signature` (Critical, report)
`void*` in a public signature where a value-erasure boundary is meant.

**Rule**: the repository's `CLAUDE.md` §System access — ownership tiers; `Docs/Patterns.md`
§Value-Erasure Boundary.

**Fix**: `byte*` behind a typed accessor, with the owner resolving the concrete storage.

### `subsystem-lazy-accessor` (Warning, report)
A subsystem interface with a `GetX()` lazy accessor, a new type declared inside a subsystem
header, or a subsystem method with no counterpart on the underlying module.

**Rule**: the repository's `CLAUDE.md` §System access — ownership tiers.

**Fix**: narrow the interface to the operations foreign code is allowed.

### `platform-coupling` (Critical, report)
A platform name — `Wayland`, `X11`, `Windows`, `Win32`, `macOS`, `Cocoa`, `POSIX` — in an
identifier, type, branch, or include outside `Engine/Modules/Platform/`. Shared modules say
*what* they need, never *which* OS provides it.

**Rule**: `Docs/StyleGuide.md` §Platform Isolation.

**Detection**: those names in engine or application source. Exempt: files under
`Engine/Modules/Platform/`, genuine platform-liaison prose, and build or CI configuration that
legitimately selects a backend.

**Fix**: route the need through the liaison or the relevant subsystem interface.

### `preprocessor-guard-in-shared-code` (Critical, report)
`#ifdef` / `#if` in shared code where `if constexpr` over a `Build::` constant is the rule — the
dead branch is eliminated at compile time but still type-checked, catching refactoring errors.

**Rule**: `Docs/StyleGuide.md` §Preprocessor Guards.

**Detection**: the directives outside platform and Vulkan modules.

**Fix**: `if constexpr (Build::IsDebugBuild)` and friends.

### `build-config-macro` (Critical, report)
A `-D` macro carrying build configuration.

**Rule**: the repository's `CLAUDE.md` §Dependencies & configuration — one resolver, all
consumers read the `Build::` constant.

**Fix**: add the constant.

### `unjustified-macro` (Warning, report)
A macro where a `constexpr`, `consteval`, concept, or template would do.

**Rule**: `Docs/StyleGuide.md` §Macros. Permitted only where no C++23 alternative exists — test
registration, third-party C API interop — and any new one documents why.

**Fix**: the compile-time construct.

### `lint-bypass-without-justification` (Warning, judgment)
`// NOLINT` or `// clang-format off` with no adjacent one-line reason.

**Rule**: `Docs/StyleGuide.md` §Lint Bypass. Work the options in order: restructure so the check
does not fire; tune `.clang-tidy` if it fires across the codebase; only then a narrow
`// NOLINT(check-name): <one-line reason>`.

**Fix**: restructure, or add the reason. A file-wide `NOLINTBEGIN`/`NOLINTEND` over a style-level
check is never the answer — that is a configuration problem (severity Critical, tier report).

### `raw-string-identity-key` (Warning, judgment)
A raw string compared for identity where a `Label` is required. Integer comparisons are
constant-time and cache-friendly.

**Rule**: `Docs/StyleGuide.md` §Labels Over Strings.

**Fix**: `inline constexpr Label` constants. Convert at API boundaries with `ToCString()` /
`ToString()`, and register through the owning module's wrapper so the hash carries the module
signature. Pass `Label` by value — `const Label&` buys nothing (Nit, mechanical).

### `misplaced-generic-helper` (Warning, report)
A generic-looking helper — a byte buffer, a formatter, an indent tracker, a string splitter, a
scope guard — parked inside the first module that consumed it.

**Rule**: `Docs/StyleGuide.md` §Helper Placement.

**Detection**: a type in a module whose name gives no hint that it is specific to that module.

**Fix**: `Core` or another lower-level shared library. Ask before committing rather than letting
the first consumer decide placement by accident.

### `hand-rolled-boilerplate` (Warning, report)
A common algorithm reimplemented at a call site — string split or trim, hashing, byte packing,
clamp/lerp math, an ad-hoc linear search, a scratch buffer, path manipulation.

**Rule**: `Docs/StyleGuide.md` §Reuse Before Reimplementation.

**Fix**: cite the existing helper in `Std`, `Core`, or the owning module. If none exists and the
need recurs, extract one into the right shared library. Swapping a hand-rolled snippet for an
existing one-call helper is judgment, not mechanical — behavior equivalence needs eyes.

### `unregistered-format-identifier` (Critical, report)
A module-local file-format magic constant, not registered in `IO::File::Identifiers`.

**Rule**: `Docs/StyleGuide.md` §File-Format Identifiers. The table carries a compile-time
uniqueness `static_assert`, so an unregistered tag is exactly the collision it exists to prevent.

**Fix**: register it through `ConvertToHex`.

### `denormalized-color` (Warning, judgment)
A color in 0–255 or hex form, or a hardcoded `RGBA{…}` duplicating an existing `Color::` /
`Palette::` constant.

**Rule**: `Docs/StyleGuide.md` §Color Constants. Color is normalized 0.0–1.0.

**Fix**: divide by 255, or use the constant.

### `themable-surface-literal` (Critical, judgment)
A literal color on a themable UI element instead of the active theme. This silently ignores the
user's theme, which is a bug rather than a style lapse.

**Rule**: `Docs/StyleGuide.md` §Color Constants.

**Fix**: read the active theme, falling back to `Palette::`.

### `hoisted-report-struct` (Warning, judgment)
A response, report, result, or status struct hoisted to top level from the entity it describes —
`LedgerEntryReport` where `Ledger::Entry::Report` is meant.

**Rule**: `Docs/StyleGuide.md` §Response and Report Struct Placement.

**Detection**: a top-level struct whose name concatenates an owning entity's name. Exempt: a
struct genuinely shared across unrelated entities, one whose nesting would create a circular
header dependency, and an aggregating cross-entity report.

**Fix**: nest it.

### `barrel-header` (Warning, report)
A `<Module>.h` re-exporting a module's entire public surface.

**Rule**: `Docs/StyleGuide.md` §Module Source Layout.

**Fix**: consumers include the specific public header, or `import` the specific
`Phoenix.<Module>`.

### `web-stack-in-ui` (Critical, report)
An HTML, JS, CSS, or HTTP surface anywhere in the Editor UI.

**Rule**: the repository's `CLAUDE.md` §UI. All Editor UI is native (Mosaic).

**Fix**: native Mosaic.

### `third-party-dependency` (Critical, report)
A third-party library that is not X11, ALSA, or Vulkan.

**Rule**: the repository's `CLAUDE.md` §Dependencies & configuration.

**Fix**: implement it, or make the case in the PR.

---

## F. Comments and documentation

### `decorative-banner` (Nit, mechanical)
A section header comment — `// ===== Helpers =====` — or an ASCII rule.

**Rule**: `Docs/StyleGuide.md` §Comments.

**Fix**: delete it; use scope and naming instead.

### `temporal-narration` (Warning, mechanical)
"previously", "now", "new", "legacy", "refactored", "was", "used to" in a comment. Future readers
see only the current code.

**Rule**: `Docs/StyleGuide.md` §Comments.

**Fix**: delete it. Why code changed belongs in the commit message and PR description.

### `stale-reference-in-comment` (Warning, mechanical)
A comment naming a file path, line number, symbol from elsewhere, commit hash, PR number, branch
name, Crucible label, date, or author tag. All of those drift the moment something is renamed,
rebased, squashed, or merged.

**Rule**: `Docs/StyleGuide.md` §Comments. If a reader should "see also" something, they can grep.

**Fix**: delete the reference, or restate it as the guarantee it stands for.

### `stacked-line-comments` (Nit, mechanical)
Multiple `//` lines forming a paragraph.

**Rule**: `Docs/StyleGuide.md` §Comments — `//` for single lines, `/* ... */` for multi-line.

**Fix**: convert, or cut to one line. Two or three lines is the ceiling; more belongs in the
commit message or a design note.

### `what-comment` (Nit, mechanical)
A comment restating the code below it — `// increment counter` above `++counter;`.

**Rule**: `Docs/StyleGuide.md` §Comments — explain *why*, never *what*.

**Fix**: delete it.

### `undocumented-public-declaration` (Warning, judgment)
An exported class, struct, free function, or public member function in a module's public header
with no purpose comment.

**Rule**: `Docs/StyleGuide.md` §Comments.

**Fix**: one line. Use `/* ... */` only when a single line cannot convey the contract.

### `unstated-cross-thread-ordering` (Warning, judgment)
Correctness resting on when something happens in another module or on another thread, with
nothing at the dependent site saying so.

**Rule**: `Docs/StyleGuide.md` §Comments; the repository's `CLAUDE.md` §Code style.

**Fix**: state the assumed ordering and the failure it prevents, phrased as the guarantee — "the
platform applies extents on the pump thread" — never as a file or line. Scoped to genuine
cross-module or cross-thread dependencies, not ordinary local sequencing.

### `todo-parenthesized-prefix` (Nit, mechanical)
`// TODO(anything): …`. The form is forbidden regardless of what the label is — Crucible labels,
saga names, PR numbers, owner handles, ticket IDs, dates, file-path shorthand.

**Rule**: `Docs/StyleGuide.md` §TODO Comments. A grep for `TODO(` should return zero hits.

**Fix**: `// TODO: …`.

### `overlong-or-narrating-todo` (Warning, judgment)
A TODO longer than a sentence, one narrating work just done, or one annotating a trivially
obvious follow-up.

**Rule**: `Docs/StyleGuide.md` §TODO Comments.

**Fix**: cut it to one sentence describing the work; if it needs a paragraph, it needs a Crucible
challenge or bug. If it describes something you would do now, do it now.

### `british-spelling` (Nit, mechanical)
British spelling in code, comments, or a commit message.

**Rule**: the repository's `CLAUDE.md` §Code style — color/center/behavior.

**Detection**: audit your own added lines; do not churn pre-existing text.

**Fix**: American English.

---

## G. Headers and trials

### `missing-pragma-once` (Warning, mechanical)
A `.h` / `.hpp` without `#pragma once`, or with traditional `#ifndef`/`#define`/`#endif` guards.

**Rule**: `Docs/StyleGuide.md` §Formatting.

**Fix**: `#pragma once`.

### `unsorted-includes` (Nit, mechanical)
Include groups misordered, or unsorted within their group (case-insensitive).

**Rule**: `Docs/StyleGuide.md` §Formatting.

**Fix**: sort and group.

### `missing-blank-line-after-scope` (Nit, mechanical)
No blank line after a `}` closing a scope, before the next non-`}` token.

**Rule**: `Docs/StyleGuide.md` §Formatting. Exempt: another closing brace, an `else` /
`else if` continuation, a trailing `;`.

**Detection**: reviewers cite this on nearly every PR that omits it. Existing violations are
debt — fix them when you touch the surrounding code, not in a standalone sweep.

**Fix**: add the blank line.

### `trial-scaffolding-in-source` (Warning, report)
Trial scaffolding, fixtures, or trial-scenario narration in a module's production sources. A
production comment states the terse *why* of the code, never a specific trial's setup.

**Rule**: the repository's `CLAUDE.md` §Testing. Trials live in the owning module's `Trials/`.

**Fix**: move it to the trial, or to the PR description for design rationale.

### `derived-fixture-path` (Warning, judgment)
A trial fixture path built from `__FILE__` or `Build::RepositoryRoot` rather than
`Trials::SourceRoot()`. `__FILE__` is a host path, so it locates nothing on a device; and under a
compiler cache keyed on `CCACHE_BASEDIR` — which CI sets — it arrives relative to the build tree,
so anything built on it passes locally and reds CI.

**Rule**: `Docs/StyleGuide.md` §Reading committed content files.

**Fix**: `Trials::SourceRoot()`, guarded before building on it.

### `source-root-forwarder` (Nit, mechanical)
A file-local helper whose whole body is `return Trials::SourceRoot();` — the same root under a
second name, per file.

**Rule**: `Docs/StyleGuide.md` §Reading committed content files.

**Fix**: call the shared entry point.

---

## Out of scope

Include-graph correctness — missing includes, forward-decl versus include choice, circular
includes, module-import hygiene — belongs to `invoke-lint-agent`. UI, Mosaic, and Ledger
architecture belongs to `ui-design-review` and its own `CHECKS.md`. Neither is audited here.
