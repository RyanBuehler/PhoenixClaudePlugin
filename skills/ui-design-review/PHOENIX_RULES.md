# Phoenix UI Architecture Rules

Reference for the ui-design-review skill. Read this file to understand the
vocabulary, architecture, and non-negotiable conventions that checks are
written against.

## Vocabulary

| Name | Role |
|---|---|
| **Mosaic** | The UI framework (retained-mode widget tree) |
| **Montage** | The 2D rendering batcher (`Montage.h`, `TextRenderer.h`) |
| **Tessera** | Atomic widget — Button, TextLabel, DragFloat, Slider, Checkbox, etc. Base class: `Tessera` (inherits `ITessera`) |
| **Canvas** | Generic container Tessera. Holds children. Base class for Panel. Layout tool with anchors, sizing, clipping. Ledger-agnostic — works in-game at runtime. |
| **Panel** | Canvas with dockable/resizable/tabbable layout machinery |
| **Signatory** | Abstract Ledger participant (non-visual). Holds Ledger& ref, RAII subscription handles, transaction metadata. Used by non-UI participants: hotkey systems, MCP bridges, auto-save services. Lives in Ledger module. |
| **Emblema** | Visual Ledger participant. Inherits from both Canvas and Signatory (multiple inheritance). IS a Canvas (in the Tessera tree, holds children, gets layout) AND a Signatory (talks to the Ledger). Lives in a bridge module separate from both Mosaic and Ledger. |
| **TesseraLease** | Current non-owning external reference to a Tessera (`weak_ptr` wrapper). Being retired in favor of `TesseraHandle` in Track A4. |
| **TesseraHandle** | Future 4-8 byte POD `{index, generation}` — the universal non-owning Tessera reference (Track A4, not yet built) |
| **TesseraRegistry** | Future central registry owning all live Tesserae in a dense sparse-set layout (Track A4, not yet built) |
| **Ledger** | The single object holding all editor runtime state. Receives Entries, processes via Transactors, maintains undo/redo. |
| **Account** | A named (`AccountName` = `Label`) section of state inside the Ledger. One per subsystem/plugin. |
| **Entry** | Polymorphic plain-data object describing a requested change. Posted to the Ledger. |
| **EntryCategory** | Value type with built-ins (`Edit`/`Selection`/`Layout`/`Import`/`Transient`) determining whether an Entry is undoable. |
| **Transactor** | Pure function `(AccountState, Entry) -> optional<AccountState>`. One per Account. Returns `nullopt` when the Entry is not its concern. |
| **Transaction** | Committed historical record written to the undo stack when an Edit-category Entry causes Accounts to change. |

## Architecture: unidirectional flow

```
User action (click, drag-release, keyboard)
  -> Emblema's callback handler
    -> ledger.Post(make_unique<MyEntry>(...))
      -> Ledger queue (thread-safe, double-buffered)

Ledger::Process() (runs once per tick on the UI DAG node)
  -> For each pending Entry:
       For each Account:
         Transactor(currentState, entry) -> optional<newState>
       If any Account changed:
         Snapshot pre-change state (lazy, only changed Accounts)
         If Entry is Edit category:
           Push Transaction to undo stack, clear redo stack
         Fire per-Account and any-change notifications

Subscribers (Emblemas, EngineBridge, telemetry)
  -> Mark for relayout / enqueue Arbiter tasks
```

### Non-negotiable rules

1. **Tesserae never touch the Ledger directly.** Only Emblemas (state-binding
   containers) post Entries and subscribe to Accounts. A `Tessera` subclass
   that imports `Ledger.h` or calls `Post()` is a Critical violation.

2. **Transactors are pure.** No I/O, no engine calls, no side effects, no
   mutable globals. They run during `Process()` and must return quickly.

3. **Engine mutations never happen inside Transactors.** The engine thread
   receives work via subscriber bridges emitting `Arbiter::Task`s, not by
   direct calls from Transactors.

4. **Commit boundary pattern.** Ephemeral editing (drag deltas, typing
   buffers, hover flags) stays local on Tesserae until a commit point
   (mouse release, Enter key, blur), at which time the Emblema posts one
   Entry to the Ledger. One undoable edit per user intent, not one per
   mouse pixel.

5. **No `weak_ptr` in the Tessera layer** once TesseraHandle lands (Track A4).
   Until then, `TesseraLease` (the current `weak_ptr` wrapper) is acceptable
   but flagged as Warning-level for future migration.

## Conventions (non-negotiable in Phoenix)

| Convention | Rule | Severity |
|---|---|---|
| Bool member prefix | `m_bVisible`, `m_bEnabled` | Critical |
| Atomic bool prefix | `m_abReleased` (not `m_bReleased`) | Critical |
| Move wrapper | `Move(x)` — never `std::move(x)` | Critical |
| Forward wrapper | `Forward<T>(x)` — never `std::forward<T>(x)` | Critical |
| Namespace | App-internal types under `namespace Application`, not app-named namespaces | Warning |
| App isolation | App code stays under `Applications/{AppName}/`, never leaks into `Modules/` or `Tools/` | Critical |
| No abbreviations | No `Btn`/`Lbl`/`Cfg`/`Mgr`/`Tmp` — use full words | Warning |
| Normalized color | All color values must be 0.0-1.0 floats. No 0-255 or hex literals. | Critical |
| Theme values | Pull from `Theme` struct, never hardcode magic color/size numbers | Warning |
| No raw owning pointers | Prefer `shared_ptr`/`unique_ptr`; `weak_ptr` for back-refs | Critical |
| TesseraLease for external refs | Use `TypedTesseraLease<T>` for external widget references | Warning |
| Get prefix on accessors | Data-returning functions use `GetXxx()` pattern | Warning |

## Tessera lifecycle hooks

These are the virtual methods on `ITessera`/`Tessera` that subclasses override:

| Hook | When it runs | What it does |
|---|---|---|
| `OnLayoutUpdate()` | After layout pass | Recompute positions, sizes |
| `OnRender(Montage&)` | Each frame during draw | Issue draw commands to Montage |
| `OnInput(const Input::Event&)` | Input event dispatch | Handle input; return `InputResult` |
| `OnFocusGained()` / `OnFocusLost()` | Focus changes | Visual feedback for focus |
| `OnMouseEnter()` / `OnMouseLeave()` | Hover tracking | Visual feedback for hover |
| `MeasureContent()` | Sizing pass | Report intrinsic content size |

### InputResult contract

`OnInput` must return one of:
- `InputResult::Ignored` — not my input, pass to next
- `InputResult::Consumed` — handled, stop propagation
- `InputResult::Captured` — this Tessera captures all future input

Silently returning `Ignored` for input that was actually handled (or vice
versa) is a Warning.

## Emblema lifecycle

Emblema subclasses override `OnAttach()` (called when added to a parent):
1. Call `Parent::OnAttach()` first (Critical to miss)
2. Wire subscriptions to Ledger Accounts via `Event::Handle` members
3. Wire Tessera callbacks to post Entries

`Event::Handle` members are RAII — cleanup is automatic on Emblema destruction.

## Theme system

`Style/Theme.h` defines the centralized palette:
- Window backgrounds, accents, selection colors, separator colors
- Typography settings, dimensions
- Accessed via `Theme::` fields, never hardcoded

`Style/ThemeManager.h` provides runtime theme swap.
