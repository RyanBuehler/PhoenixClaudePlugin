---
name: screenshot
description: Capture a screenshot from the Phoenix engine, either via console pipe or one-shot launch.
---

Capture a screenshot from the engine.

**If the engine is running** (console pipe exists):

```bash
if [ -p /tmp/phoenix-console.fifo ]; then
    echo "aurora.screenshot" > /tmp/phoenix-console.fifo
fi
```

**If the engine is not running** (one-shot capture):

```bash
./cmake-build-release/bin/Phoenix --aurora.screenshot.exit
```

After triggering, poll `Screenshots/.last-capture` for the output path (poll every 500ms, timeout 30s). Read the captured PNG file and analyze the visual output.

On headless systems, prefix with `xvfb-run`.
