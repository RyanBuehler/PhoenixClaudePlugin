---
name: frontend-validate
description: Auto-activates after UI code changes to capture screenshots and verify visual correctness; includes annotation playground for user to mark problem areas
---

After completing a logical chunk of UI, widget, or rendering code changes, verify visual correctness by rebuilding, capturing a screenshot, and evaluating the result.

## Auto-activation criteria

Activate when ALL of these are true:
- You just edited files in rendering or UI-related modules: Aurora, Glyph, Montage, Prism, or widget/panel code
- A logical set of changes is complete (not after every single edit)
- The change affects visual output (skip for purely structural changes like renames, type changes, or moving code)

## Core workflow

### 1. Rebuild

Run `/phoe:build` — this rebuilds the engine through Forge using the active profile.

### 2. Capture screenshot

Use `/phoe:screenshot` to capture the current visual state. If the engine is running via console pipe:

```bash
echo "aurora.screenshot" > /tmp/phoenix-console.fifo
```

Otherwise, one-shot capture via the Forge-managed build output (substitute `<profile>` for `editor-release` or `editor-debug`):

```bash
build-<profile>/bin/editor --aurora.screenshot.exit
```

Read `Screenshots/.last-capture` to get the output path, then read the captured PNG.

### 3. Evaluate

Analyze the screenshot:
- Describe what you see in the captured image
- Compare against what was expected from the code changes
- Check for: correct layout, proper colors, no visual artifacts, expected element visibility, correct sizing

### 4. Report

- **If correct:** Note that the visual output matches expectations and continue with the task.
- **If issues found:** Describe the discrepancies, then either fix them directly (if the cause is clear) or proceed to the annotation flow below.

## Annotation flow

Use this when issues are spotted and need user input to clarify, or when the user wants to point out specific problem areas.

### 5. Generate annotation playground

Create `.claude/frontend-debug.html` — a self-contained HTML page:

- Display the captured screenshot as the background image (use the path from `.last-capture`)
- Click-and-drag to draw rectangles over problem areas (red semi-transparent overlay)
- Click a drawn rectangle to add a text note describing the issue
- Selected rectangles can be deleted or edited
- A "Save" button that outputs `.claude/annotations.json`:

```json
{
  "screenshot": "Screenshots/capture-20260314-120000-001.png",
  "regions": [
    {
      "x": 120,
      "y": 40,
      "width": 200,
      "height": 80,
      "note": "sidebar overlaps viewport here"
    }
  ]
}
```

Provide a "Copy JSON" button as an alternative to file save.

### 6. Read annotations

Once the user saves or shares the annotations JSON:
- Parse each annotated region
- Map pixel coordinates to UI components in the engine code (use element positions, sizes, and the screenshot dimensions to correlate)
- Identify which widget/component code is responsible for each annotated region

### 7. Fix and re-verify

- Make the targeted code changes to address each annotated issue
- Rebuild and re-capture
- Compare the new screenshot against the annotations — confirm each flagged region is resolved
- If new issues appear, repeat the annotation flow
