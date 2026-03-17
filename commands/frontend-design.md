---
description: Generate an interactive HTML playground approximating engine UI for iterating on layout, colors, and sizing before applying changes to engine code.
---

Create an interactive HTML playground that approximates the target engine UI, letting the user iterate on layout and styling visually before changes are applied to engine code.

## 1. Identify UI Scope

Read the relevant widget/panel code to understand:
- Current layout structure (panels, containers, element hierarchy)
- Sizing (widths, heights, margins, padding)
- Colors (backgrounds, text, borders, accents)
- Spatial relationships between elements
- The engine's current window size and aspect ratio

## 2. Generate the Playground

Create `.claude/frontend-design.html` — a self-contained HTML/CSS/JS page:

**Layout requirements:**
- Approximate the target UI with positioned HTML elements (panels, buttons, text, dividers)
- Element IDs must map to actual widget/component names in engine code (e.g., `id="sidebar"`, `id="viewport-panel"`)
- Match the engine's current window size and aspect ratio as the initial canvas size
- Include a labels/legend mapping playground element IDs to their engine component names

**Interactive controls:**
- Drag to reposition elements (mousedown + mousemove)
- Resize panels by dragging edges/corners
- Click an element to open a color picker for its background
- Spacing/margin controls: direct input fields or sliders for selected element
- A property panel showing the selected element's current values

**State management:**
- A "Save" button that writes the current state to `.claude/design-state.json`
- A "Copy JSON" button as an alternative (since direct file writes from HTML require a server)

## 3. Present to User

Tell the user to open `.claude/frontend-design.html` in their browser. Explain:
- How to drag/resize/recolor elements
- Where to find the property panel
- How to save their design when satisfied

## 4. Apply Design to Engine Code

Once the user has saved their design (or shares the JSON):
- Read `.claude/design-state.json`
- Map each element ID back to its corresponding widget/component in engine code
- Apply the layout, color, and sizing values to the engine source
- Translate pixel values to engine units as needed (note any coordinate system differences)

## 5. Verify

Rebuild and capture a screenshot to compare against the playground mockup:

```bash
cmake --build build --config Release --parallel
```

Use `/phoe:screenshot` to capture the result and visually compare against the playground layout.

## 6. Report

Tell the user what values were applied to which engine components, and whether the screenshot matches the playground design.
