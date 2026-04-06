# bad-emblema.md: `TransformInspectorEmblema` (with violations)

## What this demonstrates

The same TransformInspectorEmblema from good-emblema.md, but with 11
annotated violations spanning all check groups. Running ui-design-review
against this file should produce exactly these 11 findings.

## The code

```cpp
// TransformInspectorEmblema.h
// VIOLATION VERSION — do not use as reference.

#pragma once

#include "Canvas.h"
#include "Tesserae/Panel.h"
#include "Ledger.h"
#include "IEntry.h"

import Phoenix;

// [V1] app-code-in-modules (Critical) — if this file lived under Modules/
// instead of Applications/Editor/, it would violate app isolation.
// (Annotated as a reminder; the path itself determines the violation.)

namespace Editor  // [V2] wrong namespace — should be `namespace Application`
{
    class SetEntityPositionEntry final : public IEntry
    {
    public:
        SetEntityPositionEntry(uint64_t InEntityId, float InX, float InY, float InZ) :
            m_EntityId(InEntityId),
            m_X(InX), m_Y(InY), m_Z(InZ)
        {}

        const char* GetName() const override { return "SetEntityPosition"; }
        // [V3] missing-nodiscard (Nit) — GetName() not marked [[nodiscard]]

        // [V4] entry-missing-category (Warning) — no GetCategory() override.
        // Uses default Edit, but should be explicit.

        uint64_t GetEntityId() const { return m_EntityId; }
        float GetX() const { return m_X; }
        float GetY() const { return m_Y; }
        float GetZ() const { return m_Z; }
        // [V3 cont.] all getters missing [[nodiscard]]

    private:
        uint64_t m_EntityId{ 0 };
        float m_X{ 0.0f };
        float m_Y{ 0.0f };
        float m_Z{ 0.0f };
    };

    class TransformInspectorEmblema : public Canvas
    {
    public:
        explicit TransformInspectorEmblema(Ledger& InLedger) :
            m_Ledger(InLedger)
        {}

        // [V5] onattach-missing-parent-call (Critical)
        void OnAttach() override
        {
            // Missing: Canvas::OnAttach() should be called first.

            m_SceneSubscription = m_Ledger.SubscribeToAccount(
                "core.scene"_L,
                [this]() { OnSceneChanged(); });

            BuildInspectorLayout();
        }

        void OnRender(Montage& DrawContext) override
        {
            // [V6] mutation-in-onrender (Critical)
            // Directly modifying engine state during render.
            if (m_bSelectionDirty)
            {
                m_SelectedEntity = Engine::GetSelectedEntity(); // engine call in render!
                m_bSelectionDirty = false;
            }

            Canvas::OnRender(DrawContext);
        }

    private:
        void BuildInspectorLayout()
        {
            auto XDrag = make_shared<DragFloat>(0.0f, 0.01f);

            // [V7] per-frame-dispatch (Warning)
            // Posts an Entry on every value change (including per-pixel drag),
            // not at the commit boundary (mouse release).
            XDrag->SetOnValueChanged(
                [this](float Val) {
                    // [V8] stdmove-instead-of-Move (Critical)
                    m_Ledger.Post(std::move(
                        make_unique<SetEntityPositionEntry>(
                            m_SelectedEntity, Val, 0.0f, 0.0f)));
                });

            AddTessera(std::move(XDrag)); // [V8 cont.] std::move again

            // [V9] hardcoded-color (Warning)
            auto Label = make_shared<TextLabel>();
            Label->SetColor(Color::RGBA(0.9f, 0.1f, 0.1f, 1.0f));
            AddTessera(std::move(Label)); // [V8 cont.]
        }

        void OnSceneChanged() { MarkNeedsLayout(); }

        // --- Members ---

        Ledger& m_Ledger;

        // [V10] emblema-holds-editor-state (Warning)
        // Selection should be in a Ledger Account, not a local member.
        uint64_t m_SelectedEntity{ 0 };
        bool m_bSelectionDirty{ true };

        Event::Handle m_SceneSubscription;

        // [V11] abbreviated-names (Warning)
        shared_ptr<DragFloat> m_XDrag;  // should be m_PositionXDragFloat
    };
} // namespace Editor
```

## Why this is bad

### Critical violations (4)

1. **`onattach-missing-parent-call`** (V5) — `OnAttach()` does not call
   `Canvas::OnAttach()`. This skips base-class initialization including
   layout setup and parent registration.

2. **`mutation-in-onrender`** (V6) — `OnRender` calls `Engine::GetSelectedEntity()`,
   reading engine state during the render phase. Render functions must only
   issue draw commands.

3. **`stdmove-instead-of-Move`** (V8) — Three instances of `std::move()`
   instead of `Move()`.

4. **`app-code-in-modules`** (V1) — Annotated as a conditional violation.
   If this file's path were under `Modules/`, it would be Critical.

### Warning violations (5)

5. **`per-frame-dispatch`** (V7) — `SetOnValueChanged` fires on every drag
   pixel, and the lambda posts an Entry each time. Should use
   `SetOnValueCommitted` (mouse release) for the commit boundary.

6. **`hardcoded-color`** (V9) — `Color::RGBA(0.9f, 0.1f, 0.1f, 1.0f)` is
   a magic color. Should use a Theme field like `Theme::ErrorColor`.

7. **`emblema-holds-editor-state`** (V10) — `m_SelectedEntity` is editor-wide
   state (current selection) held locally. Should be read from a
   `"core.selection"` Ledger Account.

8. **`entry-missing-category`** (V4) — `SetEntityPositionEntry` does not
   override `GetCategory()`. While the default `Edit` is probably correct,
   it should be explicit.

9. **`abbreviated-names`** (V11) — `m_XDrag` should be `m_PositionXDragFloat`
   or similar full-word name.

### Nit violations (1)

10. **`missing-nodiscard`** (V3) — Multiple getters (`GetName()`, `GetEntityId()`,
    `GetX()`, etc.) missing `[[nodiscard]]`.

### Namespace violation (1, Warning)

11. **Wrong namespace** (V2) — `namespace Editor` should be
    `namespace Application` per Phoenix convention.

## Related checks

Expected findings:
| # | Check | Severity | Line(s) |
|---|---|---|---|
| V1 | `app-code-in-modules` | Critical | (path-dependent) |
| V2 | `abbreviated-names` / namespace | Warning | 18 |
| V3 | `missing-nodiscard` | Nit | 30, 36-38 |
| V4 | `entry-missing-category` | Warning | (class level) |
| V5 | `onattach-missing-parent-call` | Critical | 61 |
| V6 | `mutation-in-onrender` | Critical | 73-77 |
| V7 | `per-frame-dispatch` | Warning | 89-95 |
| V8 | `stdmove-instead-of-Move` | Critical | 92, 96, 101 |
| V9 | `hardcoded-color` | Warning | 100 |
| V10 | `emblema-holds-editor-state` | Warning | 110-111 |
| V11 | `abbreviated-names` | Warning | 116 |
