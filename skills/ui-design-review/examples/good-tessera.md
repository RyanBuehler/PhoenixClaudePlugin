# good-tessera.md: `DragFloat`

## What this demonstrates

A clean atomic Tessera (float-dragging input widget) that follows every
Phoenix convention and Mosaic architecture rule. This example should produce
zero findings when the ui-design-review skill runs against it.

## The code

```cpp
// DragFloat.h — Atomic Tessera for dragging a float value.
// Lives in: Engine/Modules/Rendering/Mosaic/Source/Public/Tesserae/DragFloat.h

#pragma once

#include "Tessera.h"

import Phoenix;

class MOSAIC_API DragFloat : public Tessera
{
public:
    explicit DragFloat(float InitialValue = 0.0f, float InStep = 0.1f) :
        m_Value(InitialValue),
        m_Step(InStep)
    {}

    // --- Public API ---

    [[nodiscard]]
    float GetValue() const { return m_Value; }

    void SetValue(float NewValue)
    {
        if (m_Value == NewValue) { return; }
        m_Value = NewValue;
        m_bCacheValid = false;
        MarkNeedsLayout();
    }

    void SetStep(float NewStep) { m_Step = NewStep; }

    [[nodiscard]]
    float GetStep() const { return m_Step; }

    // Callback fired when the user commits a drag (mouse release).
    // The Emblema wires this to post an Entry to the Ledger.
    void SetOnValueCommitted(function<void(float)> Callback)
    {
        m_OnValueCommitted = Move(Callback);
    }

    // --- Tessera lifecycle ---

    void OnRender(Montage& DrawContext) override
    {
        if (!m_bCacheValid)
        {
            m_CachedText = format("{:.2f}", m_Value);
            m_bCacheValid = true;
        }

        const auto Bounds = GetBounds();
        DrawContext.DrawRect(
            Bounds,
            m_bDragging
                ? GetTheme().AccentColor
                : GetTheme().InputBackground);
        DrawContext.DrawText(m_CachedText, Bounds.GetCenter(), GetTheme().TextColor);
    }

    InputResult OnInput(const Input::Event& Event) override
    {
        if (Event.IsMouseButtonDown(Input::MouseButton::Left))
        {
            m_bDragging = true;
            m_DragStartValue = m_Value;
            return InputResult::Captured;
        }

        if (Event.IsMouseButtonUp(Input::MouseButton::Left) && m_bDragging)
        {
            m_bDragging = false;
            // Commit boundary: one Entry per user intent (drag-release),
            // not per mouse pixel. The owning Emblema fires the actual Post.
            if (m_OnValueCommitted) { m_OnValueCommitted(m_Value); }
            return InputResult::Consumed;
        }

        if (Event.IsMouseMove() && m_bDragging)
        {
            // Ephemeral: update local display value without touching the Ledger.
            m_Value = m_DragStartValue + Event.GetDragDelta().X * m_Step;
            m_bCacheValid = false;
            MarkNeedsLayout();
            return InputResult::Consumed;
        }

        return InputResult::Ignored;
    }

    UISize MeasureContent() override
    {
        // Intrinsic size for FitContent layout.
        return UISize::Pixels(80.0f, 24.0f);
    }

private:
    float m_Value{ 0.0f };
    float m_Step{ 0.1f };
    float m_DragStartValue{ 0.0f };

    bool m_bDragging{ false };
    bool m_bCacheValid{ false };
    string m_CachedText;

    function<void(float)> m_OnValueCommitted;
};
```

## Why this is good

- **No Ledger interaction.** DragFloat is an atomic Tessera. It never imports
  `Ledger.h`, never calls `Post()`. State changes flow outward via the
  `m_OnValueCommitted` callback, which the owning Emblema wires up.
- **Commit boundary pattern.** Ephemeral drag updates are local (`m_Value`
  changes on every mouse move), but the callback fires only on mouse release —
  one undo entry per user intent, not per pixel.
- **Correct `InputResult` returns.** `Captured` on drag-start (exclusive input),
  `Consumed` on drag-end and drag-move, `Ignored` for unhandled input.
- **Cache invalidation.** `m_bCacheValid = false` is set in every path that
  changes `m_Value`. `OnRender` only rebuilds the cached text when invalid.
- **`MeasureContent` override.** Supports `FitContent` sizing mode.
- **Phoenix conventions.** `Move()` not `std::move`, `m_b` prefix for bools,
  `GetXxx()` accessors, `[[nodiscard]]` on getters, Theme colors for all
  rendering, no abbreviated names.
- **No magic numbers.** Sizes use `UISize::Pixels()`, colors come from Theme.

## Related checks

This example should pass all of these (zero findings):
- `tessera-touches-ledger`
- `mutation-in-onrender`
- `oninput-silent-drop`
- `missing-measure-content`
- `missing-cache-invalidation`
- `stdmove-instead-of-Move`
- `non-normalized-color`
- `hardcoded-color`
- `per-frame-heap-allocation`
- `wrong-bool-prefix`
- `abbreviated-names`
- `missing-nodiscard`
