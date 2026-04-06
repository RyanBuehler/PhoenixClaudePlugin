# bad-tessera.md: `DragFloat` (with violations)

## What this demonstrates

The same DragFloat widget from good-tessera.md, but with 8 annotated
violations spanning Architecture, Conventions, Theme, Lifecycle, and
Performance check groups. Running ui-design-review against this file
should produce exactly these 8 findings at the annotated severities.

## The code

```cpp
// DragFloat.h — Atomic Tessera for dragging a float value.
// VIOLATION VERSION — do not use as reference.

#pragma once

#include "Tessera.h"
#include "Ledger.h"  // [V1] tessera-touches-ledger (Critical)

import Phoenix;

class MOSAIC_API DragFloat : public Tessera
{
public:
    explicit DragFloat(Ledger& InLedger, float InitialValue = 0.0f) :
        m_Ledger(InLedger),                   // [V1] Tessera holds Ledger ref
        m_Val(InitialValue)                   // [V2] abbreviated-names (Warning)
    {}

    float GetValue() const { return m_Val; } // [V3] missing-nodiscard (Nit)

    void SetValue(float NewValue)
    {
        m_Val = NewValue;
        // [V4] missing-cache-invalidation (Warning)
        // m_bCacheValid should be set to false here, but isn't.
    }

    void OnRender(Montage& DrawContext) override
    {
        // [V5] per-frame-heap-allocation (Warning)
        string DisplayText = format("{:.2f}", m_Val);

        const auto Bounds = GetBounds();
        // [V6] hardcoded-color (Warning)
        DrawContext.DrawRect(Bounds, Color::RGBA(0.2f, 0.2f, 0.3f, 1.0f));
        DrawContext.DrawText(DisplayText, Bounds.GetCenter(), GetTheme().TextColor);
    }

    InputResult OnInput(const Input::Event& Event) override
    {
        if (Event.IsMouseButtonDown(Input::MouseButton::Left))
        {
            m_bDragging = true;
            return InputResult::Captured;
        }

        if (Event.IsMouseMove() && m_bDragging)
        {
            m_Val += Event.GetDragDelta().X * 0.1f;

            // [V7] tessera-touches-ledger (Critical, second instance)
            // Tessera directly posts to the Ledger on every mouse move,
            // bypassing the Emblema layer AND the commit boundary.
            m_Ledger.Post(make_unique<SetFloatEntry>("transform.x", m_Val));

            return InputResult::Consumed;
        }

        if (Event.IsMouseButtonUp(Input::MouseButton::Left))
        {
            m_bDragging = false;
            // [V8] oninput-silent-drop (Warning)
            // This returns Ignored even though the mouse-up ends a drag.
            // Should return Consumed.
        }

        return InputResult::Ignored;
    }

    // No MeasureContent override — not flagged here because this example
    // does not set FitContent sizing mode. Would be flagged if it did.

private:
    Ledger& m_Ledger;      // [V1] raw Ledger ref on a Tessera
    float m_Val{ 0.0f };   // [V2] abbreviated name
    bool m_bDragging{ false };
    bool m_bCacheValid{ false };
};
```

## Why this is bad

### Critical violations (2 unique checks, 3 instances)

1. **`tessera-touches-ledger`** — DragFloat includes `Ledger.h`, holds a
   `Ledger&` member, and calls `Post()` directly from `OnInput`. Tesserae
   must never interact with the Ledger; this responsibility belongs to the
   owning Emblema.

### Warning violations (4)

2. **`abbreviated-names`** — `m_Val` instead of `m_Value`. Phoenix
   convention requires full words, no shorthand.

3. **`missing-cache-invalidation`** — `SetValue` modifies `m_Val` but does
   not set `m_bCacheValid = false`, so `OnRender` may draw stale cached text.

4. **`per-frame-heap-allocation`** — `string DisplayText` is constructed
   every frame in `OnRender`. Should be a cached member rebuilt only when
   the value changes.

5. **`hardcoded-color`** — `Color::RGBA(0.2f, 0.2f, 0.3f, 1.0f)` is a
   magic color literal. Should use `GetTheme().InputBackground` or similar.

6. **`oninput-silent-drop`** — The mouse-up branch sets `m_bDragging = false`
   but falls through to `return InputResult::Ignored`. Since the drag was
   active, this input was handled and should return `Consumed`.

### Nit violations (1)

7. **`missing-nodiscard`** — `GetValue()` returns by value but is not marked
   `[[nodiscard]]`.

## Related checks

Expected findings from this file:
| # | Check | Severity | Line(s) |
|---|---|---|---|
| V1 | `tessera-touches-ledger` | Critical | 7, 15, 57 |
| V2 | `abbreviated-names` | Warning | 17, 21, 50 |
| V3 | `missing-nodiscard` | Nit | 21 |
| V4 | `missing-cache-invalidation` | Warning | 24 |
| V5 | `per-frame-heap-allocation` | Warning | 32 |
| V6 | `hardcoded-color` | Warning | 37 |
| V7 | `tessera-touches-ledger` | Critical | 57 |
| V8 | `oninput-silent-drop` | Warning | 66 |
