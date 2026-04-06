# UI Design Review — Check Catalog

Each check has a stable greppable ID, severity, detection heuristic, and fix
direction. Apply every check to each in-scope file.

## Severity rubric

- **Critical** — runtime failure risk (crash, deadlock, leak, use-after-free,
  state corruption) OR non-negotiable Phoenix convention violation
- **Warning** — tech debt, maintainability smell, convention violation without
  runtime risk, performance hazard, UX defect
- **Nit** — style, consistency, documentation

---

## A. Architecture and separation of concerns

### `tessera-touches-ledger` (Critical)
A Tessera subclass imports Ledger headers or calls `Post()`, `GetState()`,
`SubscribeToAccount()`, or similar Ledger API. Only Emblemas may interact
with the Ledger.

**Detection**: class inherits from `Tessera`/`ITessera` (not `Canvas`/`Panel`/`Emblema`)
AND file includes `Ledger.h` or calls Ledger methods.

**Fix**: move Ledger interaction up to the owning Emblema. Wire Tessera
callbacks so the Emblema posts Entries in response.

### `transactor-impure` (Critical)
A Transactor function performs I/O, calls engine APIs, mutates globals, or
holds mutable captures beyond the `(AccountState, Entry)` signature.

**Detection**: Transactor lambda or function body contains file I/O, network
calls, `Engine::` calls, mutable static/global access, or side-effectful
operations.

**Fix**: make the Transactor pure. Move side effects to a subscriber that
observes Account changes and emits `Arbiter::Task`s.

### `engine-mutation-in-transactor` (Critical)
Engine state is mutated directly inside a Transactor or subscriber callback
during `Process()`, rather than via an `Arbiter::Task` on a later DAG node.

**Detection**: Transactor or `Process()`-phase callback modifies engine
objects, scene graph, or renderer state directly.

**Fix**: have the subscriber enqueue an `Arbiter::Task` describing the
engine-side mutation. The engine thread picks it up on a later DAG node.

### `onattach-missing-parent-call` (Critical)
An Emblema overrides `OnAttach()` without calling `Parent::OnAttach()` first.

**Detection**: class inherits from Emblema/Canvas, overrides `OnAttach`,
body does not contain `Parent::OnAttach()` or base-class `OnAttach()` call.

**Fix**: add `Parent::OnAttach()` as the first line of the override.

### `mutation-in-onrender` (Critical)
Engine or game state is mutated inside `OnRender()`. Render functions must
only issue draw commands to Montage — never mutate model state.

**Detection**: `OnRender` body modifies member state beyond cache flags
(`m_bCacheValid`), calls `Post()`, or writes to shared data.

**Fix**: move state mutations to `OnInput` handlers or Emblema callbacks.

### `god-widget` (Warning)
A single widget file exceeds ~500 lines, combining layout + state + logic +
drawing + serialization.

**Detection**: file defines a class inheriting from Tessera/Canvas/Panel/Emblema
AND the file exceeds 500 lines.

**Fix**: split into focused components — separate layout, state management,
and rendering concerns.

---

## B. Ownership and lifetime

### `raw-owning-pointer` (Critical)
A raw pointer (`T*`) is used for ownership — allocating with `new` and
storing without `unique_ptr`/`shared_ptr`.

**Detection**: `new T(...)` stored in a raw pointer member or local without
immediate wrapping in a smart pointer.

**Fix**: use `make_unique<T>(...)` or `make_shared<T>(...)`.

### `shared-from-this-in-constructor` (Critical)
`shared_from_this()` called in a constructor. The `shared_ptr` control block
does not exist yet during construction.

**Detection**: constructor body contains `shared_from_this()`.

**Fix**: move the call to `OnAttach()` or a post-construction init method.

### `lambda-cycle-capture` (Critical)
A lambda stored in a child widget captures `this` (the parent) by strong
reference, creating a reference cycle that prevents destruction.

**Detection**: lambda capture list contains `this` or `shared_ptr` to the
enclosing widget, AND the lambda is stored in a child's callback slot.

**Fix**: capture `weak_ptr` and `lock()` inside the lambda body, or use
`TesseraLease` for the reference.

### `stored-lock-result` (Critical)
The result of `weak_ptr::lock()` is stored as a member variable rather than
used locally. This defeats the purpose of weak references.

**Detection**: member variable of type `shared_ptr` assigned from
`some_weak.lock()`.

**Fix**: call `lock()` at point of use, check for null, use immediately.

---

## C. Phoenix non-negotiable conventions

### `stdmove-instead-of-Move` (Critical)
`std::move(x)` used instead of Phoenix's `Move(x)` wrapper.

**Detection**: literal `std::move(` in code.

**Fix**: replace with `Move(`.

### `stdforward-instead-of-Forward` (Critical)
`std::forward<T>(x)` used instead of Phoenix's `Forward<T>(x)` wrapper.

**Detection**: literal `std::forward<` in code.

**Fix**: replace with `Forward<`.

### `non-normalized-color` (Critical)
Color values using 0-255 integer range or hex literals instead of 0.0-1.0
normalized floats.

**Detection**: color constructor or assignment with values > 1.0, or hex
color literals like `0xFF0000`.

**Fix**: convert to normalized floats (divide by 255.0f).

### `app-code-in-modules` (Critical)
Application-specific code placed under `Modules/` or `Tools/` instead of
`Applications/{AppName}/`.

**Detection**: file path is under `Modules/` but contains app-specific logic,
includes app headers, or uses `namespace Application`.

**Fix**: move the file to `Applications/{AppName}/`.

### `wrong-bool-prefix` (Warning)
Bool member missing `m_b` prefix, or atomic bool missing `m_ab` prefix.

**Detection**: `bool m_[^b]` or `atomic_bool m_[^a]` member declaration.

**Fix**: rename with correct prefix (`m_bFoo` for bool, `m_abFoo` for atomic).

### `abbreviated-names` (Warning)
Shorthand/abbreviated variable or type names like `Btn`, `Lbl`, `Cfg`,
`Mgr`, `Tmp`.

**Detection**: identifiers containing common abbreviations.

**Fix**: use full words — `Button`, `Label`, `Configuration`, `Manager`, `Temporary`.

---

## D. Theme and style system

### `hardcoded-color` (Warning)
Color literal used directly instead of pulling from `Theme` struct fields.

**Detection**: `Color::RGBA(...)` or similar with literal float arguments,
not referencing a `Theme::` field.

**Fix**: use the appropriate `Theme::` field (e.g., `Theme::ButtonHoverBackground`).

### `hardcoded-magic-number` (Warning)
Magic pixel sizes, offsets, or spacing values hardcoded where a Theme
dimension value exists.

**Detection**: literal numeric values for sizes, padding, margins in layout
or render code.

**Fix**: define in Theme or use existing Theme dimension fields.

---

## E. Unidirectional flow / Ledger rules

### `transactor-side-effects` (Critical)
Identical to `transactor-impure` — listed separately for cross-reference
from the Ledger rules context. See A.`transactor-impure`.

### `emblema-holds-editor-state` (Warning)
An Emblema holds editor-wide state (selection, tool mode, active entity) as
a local member instead of reading it from a Ledger Account.

**Detection**: Emblema member variables that look like selection sets, tool
mode enums, or active-entity IDs that should be in a shared Account.

**Fix**: move the state to a Ledger Account; have the Emblema subscribe.

### `per-frame-dispatch` (Warning)
An Emblema posts Entries from a per-frame or per-mouse-move handler without
a commit boundary (mouse release, Enter, blur).

**Detection**: `Post()` called inside `OnRender()`, `OnInput()` mouse-move
handler, or any per-frame callback.

**Fix**: buffer ephemeral state locally on the Tessera; post one Entry at
the commit point.

### `entry-missing-category` (Warning)
An Entry subclass does not override `GetCategory()` and silently uses the
default (`Edit`). This may be intentional but should be explicit.

**Detection**: class inherits from `IEntry`, does not override `GetCategory()`.

**Fix**: add an explicit `GetCategory()` override, even if returning `Edit`.

---

## F. Lifecycle and input

### `oninput-silent-drop` (Warning)
`OnInput` handles input but returns `InputResult::Ignored`, or ignores
input it should consume and returns nothing meaningful.

**Detection**: `OnInput` body has conditional logic that handles some events
but the return path returns `Ignored` in all cases.

**Fix**: return `Consumed` or `Captured` when the Tessera actually handles
the event.

### `missing-measure-content` (Warning)
A Tessera that uses `FitContent` sizing mode but does not override
`MeasureContent()`.

**Detection**: sizing mode set to `FitContent` (in constructor or setup),
no `MeasureContent` override present.

**Fix**: implement `MeasureContent()` returning the intrinsic content size.

### `missing-cache-invalidation` (Warning)
A Tessera uses a cache pattern (`m_bCacheValid`, `m_CachedVertices`, etc.)
but does not invalidate the cache when state changes.

**Detection**: cache flag exists but state-mutating methods do not set it
to false.

**Fix**: add `m_bCacheValid = false;` in every method that changes the
cached state.

---

## G. Performance

### `per-frame-heap-allocation` (Warning)
`std::string`, `std::vector`, or other heap-allocating types constructed
every frame in `OnRender` or hot render paths.

**Detection**: local `string`/`vector`/`map` construction inside `OnRender`
or a method called every frame.

**Fix**: move to a member, reuse with `clear()`, or use stack-allocated
alternatives.

### `god-widget-lines` (Warning)
Duplicate of `god-widget` — see A. Listed for cross-reference from the
performance context (large files are harder to optimize).

---

## H. Code-detectable UX heuristics

### `icon-button-missing-tooltip` (Warning)
A Button that uses only an icon (no visible text label) but has no tooltip.

**Detection**: Button construction with icon but no `SetTooltip()` call.

**Fix**: add `SetTooltip("description")`.

### `destructive-action-missing-confirm` (Warning)
A destructive action (Delete, Remove, Clear, Reset) wired directly to a
callback without a confirmation dialog.

**Detection**: callback name or connected Entry name contains "Delete"/
"Remove"/"Clear"/"Reset" with no dialog/confirmation guard.

**Fix**: wrap in a confirmation dialog before executing.

### `small-hit-target` (Nit)
A clickable widget with a size literal smaller than 16 pixels in either
dimension.

**Detection**: `SetSize` or constructor with pixel values < 16 on a
Button/Checkbox/interactive Tessera.

**Fix**: increase to at least 16x16 pixels for comfortable click targets.

---

## I. Style and documentation

### `missing-nodiscard` (Nit)
A const getter that returns by value or reference but is not marked
`[[nodiscard]]`.

**Detection**: const member function returning non-void without
`[[nodiscard]]`.

**Fix**: add `[[nodiscard]]`.

### `missing-doc-comment` (Nit)
A public API method on a Tessera/Emblema/Canvas with no documentation
comment.

**Detection**: public method declaration with no preceding `//` comment.

**Fix**: add a brief doc comment.
