---
name: screenshot
description: Capture a screenshot from the Phoenix engine, either via console pipe or one-shot launch.
---

Capture a screenshot from the engine using whichever method is available.

Capture through the engine's own `aurora.screenshot` path, not an external screenshot app
(`gnome-screenshot`, `scrot`, `import`, `grim`, `spectacle`, `flameshot`) — external apps capture
window chrome and race the swapchain.

## Engine commands

- `aurora.screenshot` — capture from a running engine. Parameters: `frames` (default 1),
  `countdown` (seconds of delay, default 0).
- `aurora.screenshot_and_shutdown` — capture once, then shut the engine down. This is the
  one-shot form.

Captures land in `Screenshots/` as `capture-YYYYMMDD-HHMMSS-NNN.png`, and each successful capture
writes its full path to `Screenshots/.last-capture` — read that file rather than guessing a
timestamp.

## 1. Capture

**If the engine is running** with a console pipe (launched with `--console-pipe=PATH`), write the
command to the pipe. The pipe takes one command per line, queued and run on the main thread each
tick:

```bash
if [ -p /tmp/phoenix-console.fifo ]; then
    echo "aurora.screenshot" > /tmp/phoenix-console.fifo
fi
```

**If the engine is not running**, launch the editor for a one-shot capture. Build it with
`/phoe:build` (`editor-release` for a release GUI run, or `editor`) and take the binary's path from
the build result's `output_path` — the tree under `Applications/Forge/.forge/` is named per profile
and host, so do not hardcode it:

```bash
"$EDITOR_BIN" --aurora.screenshot_and_shutdown
```

To keep it running for further captures instead, launch it with
`--console-pipe=/tmp/phoenix-console.fifo` and send commands as above.

Capture needs a display server (X11 or Wayland). On a headless host, prefix the launch with
`xvfb-run`.

## 2. Retrieve

Poll `Screenshots/.last-capture` for the output path (every 500ms, timeout 30s). Read the captured
PNG and analyze the visual output.

## 3. Report

Tell the user the screenshot path and describe what was captured.
