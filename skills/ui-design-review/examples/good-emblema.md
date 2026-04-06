# good-emblema.md: `TransformInspectorEmblema`

## What this demonstrates

A clean Emblema (state-binding module) that subscribes to Ledger Accounts,
builds a Tessera subtree, and wires Tessera callbacks to post Entries. This
is the canonical pattern for connecting UI to the Ledger. It should produce
zero findings.

## The code

```cpp
// TransformInspectorEmblema.h
// Lives in: Applications/Editor/Source/Public/TransformInspectorEmblema.h

#pragma once

#include "Canvas.h"
#include "Tesserae/Panel.h"
#include "Ledger.h"
#include "IEntry.h"

import Phoenix;

namespace Application
{
    // Entry posted when the user commits a position change via the inspector.
    class SetEntityPositionEntry final : public IEntry
    {
    public:
        SetEntityPositionEntry(uint64_t InEntityId, float InX, float InY, float InZ) :
            m_EntityId(InEntityId),
            m_X(InX),
            m_Y(InY),
            m_Z(InZ)
        {}

        [[nodiscard]]
        const char* GetName() const override { return "SetEntityPosition"; }

        // Edit category (undoable) — default, no override needed.

        [[nodiscard]]
        uint64_t GetEntityId() const { return m_EntityId; }

        [[nodiscard]]
        float GetX() const { return m_X; }

        [[nodiscard]]
        float GetY() const { return m_Y; }

        [[nodiscard]]
        float GetZ() const { return m_Z; }

    private:
        uint64_t m_EntityId{ 0 };
        float m_X{ 0.0f };
        float m_Y{ 0.0f };
        float m_Z{ 0.0f };
    };

    // TransformInspectorEmblema displays and edits the position of the
    // currently selected entity. It subscribes to the "core.scene" and
    // "core.selection" Accounts and posts SetEntityPositionEntry when the
    // user commits a drag on any of the three DragFloat Tesserae.
    class TransformInspectorEmblema : public Canvas
    {
    public:
        explicit TransformInspectorEmblema(Ledger& InLedger) :
            m_Ledger(InLedger)
        {}

        void OnAttach() override
        {
            // 1. Call parent first (Critical convention).
            Canvas::OnAttach();

            // 2. Subscribe to Ledger Accounts.
            m_SceneSubscription = m_Ledger.SubscribeToAccount(
                "core.scene"_L,
                [this]() { OnSceneChanged(); });

            m_SelectionSubscription = m_Ledger.SubscribeToAccount(
                "core.selection"_L,
                [this]() { OnSelectionChanged(); });

            // 3. Build the Tessera subtree.
            BuildInspectorLayout();
        }

        void OnRender(Montage& DrawContext) override
        {
            // Read current state from the Ledger (read-only snapshot access).
            UpdateDisplayFromLedgerState();

            // Render children (Tesserae handle their own drawing).
            Canvas::OnRender(DrawContext);
        }

    private:
        void BuildInspectorLayout()
        {
            m_PositionXDragFloat = make_shared<DragFloat>(0.0f, 0.01f);
            m_PositionYDragFloat = make_shared<DragFloat>(0.0f, 0.01f);
            m_PositionZDragFloat = make_shared<DragFloat>(0.0f, 0.01f);

            // Wire commit callbacks: Tessera -> Emblema -> Ledger.
            // The DragFloat fires m_OnValueCommitted on mouse release.
            // The Emblema posts one Entry per commit, not per pixel.
            m_PositionXDragFloat->SetOnValueCommitted(
                [this](float NewValue) { PostPositionChange(NewValue, GetY(), GetZ()); });
            m_PositionYDragFloat->SetOnValueCommitted(
                [this](float NewValue) { PostPositionChange(GetX(), NewValue, GetZ()); });
            m_PositionZDragFloat->SetOnValueCommitted(
                [this](float NewValue) { PostPositionChange(GetX(), GetY(), NewValue); });

            AddTessera(m_PositionXDragFloat);
            AddTessera(m_PositionYDragFloat);
            AddTessera(m_PositionZDragFloat);
        }

        void PostPositionChange(float NewX, float NewY, float NewZ)
        {
            // One Entry per user intent (the commit boundary).
            m_Ledger.Post(make_unique<SetEntityPositionEntry>(
                m_SelectedEntityId, NewX, NewY, NewZ));
        }

        void OnSceneChanged()
        {
            // Re-read scene state and update display on next render.
            MarkNeedsLayout();
        }

        void OnSelectionChanged()
        {
            // Read the current selection from the Ledger.
            // (Implementation would read from core.selection Account here.)
            MarkNeedsLayout();
        }

        void UpdateDisplayFromLedgerState()
        {
            // Read-only access to Account state. Never mutates.
            const auto* SceneState = m_Ledger.GetState("core.scene"_L);
            if (SceneState == nullptr) { return; }

            // Update DragFloat display values (ephemeral — no Entries posted).
            // (Concrete implementation would cast and extract entity position.)
        }

        [[nodiscard]]
        float GetX() const { return m_PositionXDragFloat ? m_PositionXDragFloat->GetValue() : 0.0f; }

        [[nodiscard]]
        float GetY() const { return m_PositionYDragFloat ? m_PositionYDragFloat->GetValue() : 0.0f; }

        [[nodiscard]]
        float GetZ() const { return m_PositionZDragFloat ? m_PositionZDragFloat->GetValue() : 0.0f; }

        // --- Members ---

        Ledger& m_Ledger;
        uint64_t m_SelectedEntityId{ 0 };

        // RAII subscription handles — cleanup on destruction.
        Event::Handle m_SceneSubscription;
        Event::Handle m_SelectionSubscription;

        // Child Tesserae (owned by Canvas via AddTessera).
        shared_ptr<DragFloat> m_PositionXDragFloat;
        shared_ptr<DragFloat> m_PositionYDragFloat;
        shared_ptr<DragFloat> m_PositionZDragFloat;
    };
} // namespace Application
```

## Why this is good

- **Emblema owns Ledger interaction, Tesserae do not.** DragFloat never
  sees the Ledger; the Emblema wires `SetOnValueCommitted` callbacks that
  post Entries.
- **`OnAttach` calls `Canvas::OnAttach()` first.** The critical parent-call
  convention is respected.
- **RAII subscriptions via `Event::Handle`.** `m_SceneSubscription` and
  `m_SelectionSubscription` auto-unsubscribe when the Emblema is destroyed.
- **Commit boundary.** DragFloat handles ephemeral drag state locally; the
  Emblema only posts on the committed value (mouse release callback).
- **`namespace Application`.** App-internal types use the correct namespace.
- **Entry declares `GetName()`.** `SetEntityPositionEntry` has a stable name
  for logging and Transaction records.
- **Entry uses default `Edit` category** (undoable). Appropriate for position
  changes that the user should be able to undo.
- **`[[nodiscard]]` on all getters.** Clean accessor discipline.
- **No magic numbers, no hardcoded colors, no abbreviations.**
- **`Move()` not `std::move()`.** Phoenix convention throughout.

## Related checks

This example should pass all of these (zero findings):
- `tessera-touches-ledger`
- `onattach-missing-parent-call`
- `mutation-in-onrender`
- `emblema-holds-editor-state`
- `per-frame-dispatch`
- `stdmove-instead-of-Move`
- `non-normalized-color`
- `hardcoded-color`
- `wrong-bool-prefix`
- `abbreviated-names`
- `lambda-cycle-capture`
- `missing-nodiscard`
