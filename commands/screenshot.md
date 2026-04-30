---
description: Capture a screenshot from the Phoenix engine, either via console pipe or one-shot launch.
---

Capture a screenshot from the engine using whichever method is available.

## 1. Capture

**If the engine is running** (console pipe exists):

```bash
if [ -p /tmp/phoenix-console.fifo ]; then
    echo "aurora.screenshot" > /tmp/phoenix-console.fifo
fi
```

**If the engine is not running** (one-shot capture):

Detect the active Forge profile from existing build directories and launch the editor via its profile-suffixed path (`build-editor-debug/`, `build-editor-release/`):

```bash
for PROFILE in editor-release editor-debug; do
    if [ -x "build-${PROFILE}/bin/editor" ]; then
        build-${PROFILE}/bin/editor --aurora.screenshot.exit
        break
    fi
done
```

If neither profile directory exists, run `/phoe:build` first.

On headless systems, prefix the editor invocation with `xvfb-run`.

## 2. Retrieve

Poll `Screenshots/.last-capture` for the output path (poll every 500ms, timeout 30s). Read the captured PNG file and analyze the visual output.

## 3. Report

Tell the user the screenshot path and describe what was captured.
