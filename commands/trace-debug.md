---
description: Instrument code with Scribe breadcrumb traces, rebuild, reproduce, read logs, and diagnose. A structured debugging workflow using temporary trace markers.
---

Debug an issue by instrumenting code with Scribe trace breadcrumbs, then reading the resulting logs to understand runtime behavior.

## 1. Identify the Expected Path

Read the relevant code and map out the functions and branches you expect to execute during the scenario. Note decision points, early returns, and conditional branches — these are your instrumentation targets.

## 2. Instrument with Breadcrumb Traces

Add `Scribe::LogF()` calls at key points along the expected path. Wrap every instrumentation block in region markers for cleanup:

```cpp
// #region CLAUDE_DEBUG
Scribe::LogF("Claude"_L, Scribe::LogLevel::Log, "OrderSystem::Process — entered, count=%d", count);
// #endregion CLAUDE_DEBUG
```

Guidelines:
- Use `Scribe::LogF("Claude"_L, Scribe::LogLevel::Log, ...)` — this auto-creates `Logs/Claude.log` with no registration needed
- Do NOT use the `Trace()` wrapper — it requires a compile-time category Tag, which `"Claude"_L` is not. `Scribe::LogF` accepts any runtime `Label` directly
- Use `LogLevel::Log` (not `LogLevel::Trace`) — Trace-level messages are subject to the Scribe category filter and may be silently dropped for unregistered categories
- Messages should be short descriptive breadcrumbs: what function, what state, relevant variable values
- Instrument at: function entry, branch decisions, loop iterations (with counts), early returns, error paths
- Place traces to distinguish which branches execute and which are skipped

## 3. Rebuild

```bash
cmake --build build --config Release --parallel
```

Fix any compilation errors in the instrumentation before proceeding.

## 4. Reproduce

Run the engine or test to trigger the scenario:

```bash
# For engine scenarios:
./build/bin/PhoenixEditor

# For test scenarios:
ctest --test-dir build -C Release -R "TestName" --output-on-failure
```

Ask the user only if you cannot trigger the scenario independently (e.g., it requires specific user interaction).

## 5. Read Logs

Read `Logs/Claude.log` and correlate:
- Which breadcrumbs appeared — confirms that code path executed
- Which breadcrumbs are missing — narrows the problem to a specific branch or function
- The order of breadcrumbs — reveals unexpected execution flow
- Variable values in messages — shows runtime state

## 6. Diagnose or Re-instrument

If the root cause is clear from the log analysis, fix it. Otherwise:
- Add more granular traces in the narrowed-down area
- Repeat from step 3 (rebuild, reproduce, read)
- Each iteration should narrow the search space

## 7. Clean Up

After fixing the issue, remove all instrumentation and the debug log:

```bash
grep -rl "#region CLAUDE_DEBUG" .
```

For each file, delete every line from `// #region CLAUDE_DEBUG` through `// #endregion CLAUDE_DEBUG` (inclusive). Then delete the debug log:

```bash
rm -f Logs/Claude.log
```

Verify no markers remain:

```bash
grep -r "CLAUDE_DEBUG" . --include="*.cpp" --include="*.cppm" --include="*.h"
```

## 8. Report

Tell the user the root cause, the fix applied, and confirm all debug instrumentation has been removed.
