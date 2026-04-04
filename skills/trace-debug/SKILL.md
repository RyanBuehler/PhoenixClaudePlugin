---
name: trace-debug
description: Use when investigating a reproducible Phoenix C++ bug whose root cause is unclear from reading, and you need to narrow down where state first goes wrong by instrumenting the suspect region with Scribe breadcrumb traces. Triggers include "trace this", "narrow down where", "add logging to figure out", "why isn't this firing", "which branch runs", "bisect this", or any situation where you'd reach for printf-style debugging in a running Phoenix subsystem. Not for crashes with stack traces (use invoke-debugger-agent), non-reproducible bugs until stabilized, or bugs already understood from reading.
---

# Trace Debug — Bisecting Phoenix Bugs with Scribe Breadcrumbs

## Overview

When you can reproduce a Phoenix bug but cannot see where state first goes wrong, instrument the suspect region with Scribe breadcrumb traces and bisect it by judgment — not by sprinkling `Scribe::LogF` calls everywhere and reading the wreckage.

**Core principle:** Every trace you add tests a specific claim about runtime behavior. If you cannot state what you expect to see, you are not debugging — you are logging.

## The Core Rule

```
NO TRACE WITHOUT A STATED HYPOTHESIS
NO FIX UNTIL BISECTION TERMINATES
NO REPORT UNTIL THE CLEANUP AUDIT GREP RETURNS EMPTY
```

Violating the letter of these rules is violating the spirit of the workflow.

## Auto-activation criteria

Activate when ALL of these are true:
- The bug is reproducible (deterministic repro exists, or you can stabilize it with the Phase 1 steps below).
- The root cause is unclear from reading the source — you cannot point at a line and say "that's it."
- The bug is in Phoenix C++ code (module, engine, or subsystem behavior), not a crash with a stack trace.
- Stepping through with a debugger is impractical (event-driven flow, long async chains, tick-rate-dependent behavior, headless CI-only repro).

Do **not** activate for:
- Crashes, segfaults, or any bug with a usable stack trace → use `invoke-debugger-agent`.
- Non-reproducible / flaky failures → stabilize first (Phase 1.1), or escalate to `invoke-concurrency-agent` if race-related.
- Visual / rendering regressions → use the `frontend-validate` skill.
- Bugs you already understand from reading → just fix them; bisection has no signal when you know the answer.

## Phase 1 — Frame the Hunt

Complete every step before placing a single trace.

### 1.1 Confirm reproducibility

Run the repro steps twice unchanged. The bug must fire both times. If it fires once and passes once, **STOP** — a non-deterministic bug will poison every bisection round because a missing trace cannot be distinguished from "didn't trigger this run."

Stabilize by narrowing the environment: pin random seeds (`std::mt19937`), force a single tick rate, disable subsystems that introduce asynchrony, or isolate the failing test via `ctest --test-dir build -C Release -R "<name>" --repeat until-pass:10` to confirm it fails 10/10 times. If you cannot stabilize it, hand off to `invoke-concurrency-agent`.

### 1.2 State the hypothesis in one sentence

Before placing any trace, write down:

> "I expect **X** to happen in function **F** when condition **C** holds, but I observe **Y** instead."

If you cannot phrase it this way, read more code first — you don't know the question yet, and traces placed without a question produce logs without an answer.

### 1.3 Check recent changes to the suspect region

Recent edits in the suspect code are the highest-prior hypothesis by a wide margin. Run:

```bash
git log -p -- <path/to/suspect.cpp>
git log -S<SymbolName>
```

Read the last 10–20 commits touching the file, and any commit that added or removed the specific symbol involved. This step frequently ends the hunt before a single trace is placed.

### 1.4 Define the suspect region

Identify `start` — the outermost function where you believe the bug is contained — and `end` — the innermost observable symptom (the line where the wrong value is first visible, the event that fails to fire, the return value that is wrong). Everything between them is your search space, written as `[start, end]`. You will be discarding halves of this region.

## Phase 2 — Instrument Boundaries and One Midpoint

**Place exactly three traces per bisection round: at `start`, at `end`, and at one judgment-chosen structural midpoint between them.**

### 2.1 The exact Scribe incantation

Every trace follows this pattern, wrapped in region markers for cleanup:

```cpp
// #region CLAUDE_DEBUG
Scribe::LogF("Claude"_L, Scribe::LogLevel::Log,
             "OrderSystem::Process entry Count=%d State=%d", Count, State);
// #endregion CLAUDE_DEBUG
```

Hard rules — do not deviate:

- Use `Scribe::LogF`, **not** the `Trace()` wrapper. `Trace()` requires a compile-time `Tag`; `"Claude"_L` is a runtime `Label`, which only `LogF` accepts.
- Use `Scribe::LogLevel::Log`, **not** `LogLevel::Trace`. Trace-level messages are silently dropped for unregistered categories by the Scribe filter — you will see nothing.
- `"Claude"_L` auto-creates `Logs/Claude.log` with zero registration required.
- Every trace wrapped in `// #region CLAUDE_DEBUG` / `// #endregion CLAUDE_DEBUG`. Cleanup scans for the markers, so a missing marker becomes permanent dead code.
- Include variable values in the format string (counts, enum values, non-null pointer checks). A trace without state is worth half a trace.

### 2.2 Choosing the midpoint — structural, not arithmetic

**Do not divide by line number.** Pick a natural structural boundary roughly midway between `start` and `end` in the control flow: the return from a significant function call, the top of a `for` loop, the `true` branch of an `if`, a call into a different subsystem, an `Arbiter` event publication, a `Subsystem::Get<>()` lookup, the release of a lock.

Structural boundaries are where bugs hide (data crosses an interface, invariants break, a branch is taken wrong) and they are where your eye naturally rests. If two candidates are equally "midway," pick the one that crosses a module boundary or a state mutation — bugs cluster at those seams. See `references/placement-heuristics.md` for the full priority list when the choice isn't obvious.

### 2.3 Build and reproduce

```bash
cmake --build build --config Release --parallel
```

Never use `-j` or `-j$(nproc)` — that's a hard project rule. For test-case repros:

```bash
ctest --test-dir build -C Release -R "<TestName>" --output-on-failure
```

For engine repros: `./build/bin/editor`. If the repro requires interactive steps, ask the user for them once; after that, rebuild-reproduce autonomously each round.

**Fix compile errors in the instrumentation before re-reading code.** A trace that does not compile teaches you nothing.

## Phase 3 — Narrow via Bisection

Read `Logs/Claude.log`. Match the output against this table — it is the heart of the skill:

| Observation in `Logs/Claude.log` | Conclusion about bug location | Next round action |
|---|---|---|
| `start` present, `mid` present, `end` absent | Bug is in `[mid, end]` — symptom fires after `mid` | Retain second half. New midpoint between `mid` and `end`. Remove the old `start` trace. |
| `start` present, `mid` absent, `end` absent | Bug is in `[start, mid]` — control flow never reached `mid` | Retain first half. New midpoint between `start` and `mid`. Remove the old `end` trace. |
| `start` present, `mid` present **with wrong state**, `end` present | Bug is upstream of `mid`, or *at* `mid` — state was already corrupt by `mid` | Retain `[start, mid]`; treat the current `mid` as the new `end`. |
| `start` absent | Repro never enters the suspect region | Your region is wrong. Move `start` outward — do not keep bisecting blindly. |
| All three present, all state correct | Bug is not in this region, OR Phase 1.1 determinism was violated | Widen the region OR re-verify reproducibility before continuing. |

You are not running a binary search algorithm. You are running an experiment per round. If a round teaches you nothing — say, because the midpoint sat in a cold path the repro doesn't exercise — that is data: the region is wrong, not the bisection. Re-select a midpoint on the hot path of this specific repro.

**Remove traces you are discarding at each round.** A twenty-trace log is a log-flood, not a bisection. Before rebuilding for round N+1, delete the `#region CLAUDE_DEBUG` blocks that no longer bound your search space.

## Phase 4 — Terminate

Stop bisecting when **any** of these holds:

- You have narrowed the suspect region to roughly 1–5 consecutive statements, a single if/else, or a single loop iteration. Further bisection has diminishing returns — read the code.
- You observe *state first becoming wrong* between two adjacent traces. That gap is the bug. Stop.
- You have formed a concrete, specific root-cause hypothesis (not "somewhere in Process," but "the `Release` build's NRVO elides the side-effect, so the committed count stays zero"). Switch from bisection to verification.
- You have done ≥5 rounds without the region shrinking. Something is wrong with the method — most likely Phase 1.1 determinism was violated, or you have a Heisenbug. Jump to the Heisenbug section, or escalate to `invoke-debugger-agent`.

Do not fix symptoms before bisection terminates. A fix applied mid-bisection destroys the signal for the next round and usually turns out to be the wrong fix.

## Phase 5 — Clean Up and Audit

The cleanup is not honor-system. The audit grep is the source of truth.

1. Find every region marker you added:

    ```bash
    grep -rn "CLAUDE_DEBUG" . --include="*.cpp" --include="*.cppm" --include="*.h" --include="*.hpp"
    ```

2. For each hit, delete every line from `// #region CLAUDE_DEBUG` through the matching `// #endregion CLAUDE_DEBUG`, inclusive.

3. Delete the debug log:

    ```bash
    rm -f Logs/Claude.log
    ```

4. **Re-run the grep. It MUST return zero.** If anything comes back, stop and clean up. Do not report.

    ```bash
    grep -rn "CLAUDE_DEBUG" . --include="*.cpp" --include="*.cppm" --include="*.h" --include="*.hpp"
    ```

5. Format any files you touched:

    ```bash
    python Tools/format.py --files=staged
    ```

6. Rebuild once to confirm the code compiles without the instrumentation. A compile error here means you deleted a brace along with a marker.

7. Only after the audit grep is empty and the rebuild passes, report to the user with: the root cause, the fix applied, and explicit confirmation that all instrumentation is removed.

**Do not report success, do not commit, do not hand control back until the audit grep is empty.**

## Heisenbug Handling

If traces cause the bug to vanish, reappear elsewhere, or change shape, you have a Heisenbug. `Scribe::LogF` is not free — it formats, flushes, and crosses a mutex. Hot loops, lock-free paths, and Arbiter event dispatch are especially vulnerable.

**First mitigation — reduce trace overhead.** Drop format arguments (log a raw int or enum instead of a formatted string), remove traces from the hottest inner loop, and retry. If the bug returns, the removed trace was the disturbance — the bug lives inside the region you just stripped.

**Second mitigation — dual-run verification.** Run the repro WITH and WITHOUT your current traces. If WITHOUT fails and WITH passes, your traces are masking the bug; their placement itself is a clue (usually: they impose an ordering that a race relied on to be observable).

**Third mitigation — escalate.** At this point, print-style debugging is the wrong tool. Hand off to `invoke-debugger-agent` (GDB/LLDB with hardware watchpoints) or `invoke-concurrency-agent` (TSAN, memory ordering analysis). Leave "traces mask this bug" in your report — that fact alone narrows the category.

See `references/heisenbugs.md` for the full taxonomy of trace-induced vanishings and per-category mitigations.

## Anti-Patterns

| Anti-pattern | Why it fails | Do this instead |
|---|---|---|
| Log-flooding (20+ traces across 8 files in round 1) | Signal buried in noise; you'll read logs instead of debugging | Three traces per round: `start`, `mid`, `end` |
| Bisecting without a stated hypothesis | Every result feels "interesting"; you'll wander for hours | Phase 1.2 — write the sentence first |
| Bisecting a non-deterministic bug | Missing trace ≠ wrong branch; signal is ambiguous | Phase 1.1 — stabilize or escalate |
| Instrumenting a race-sensitive hot loop | Trace imposes ordering; bug vanishes (Heisenbug) | Reduce overhead, escalate to `invoke-concurrency-agent` |
| Trusting yourself on cleanup | Traces ship to `main`; `Logs/Claude.log` pollutes the workspace | Phase 5 audit grep MUST return empty |
| Calculating "line N/2" as midpoint | Splits nothing meaningful; both halves look the same | Structural boundaries: function calls, branches, locks, event sites |
| Fixing before bisection terminates | You're patching a symptom, not the root | Phase 4 terminate criteria; fix after, not during |
| Using `Trace()` wrapper or `LogLevel::Trace` | Filtered silently; you will see nothing in `Logs/Claude.log` | `Scribe::LogF("Claude"_L, Scribe::LogLevel::Log, ...)` verbatim |
| Adding traces and not removing discarded ones between rounds | Log grows each round; old traces drown the new ones | Remove traces outside the current search region before rebuilding |

## Worked Example

*Hypothetical — replace with a real Phoenix bug when convenient.*

**Symptom:** In the editor, selecting an item from the inventory panel no longer applies its effect. The selection UI lights up correctly but the game state doesn't change. The `ApplyItem` path is suspect but the file is 800 lines.

**Phase 1.2 hypothesis:** *"I expect `InventoryModule::ApplyItem` to publish an `ItemApplied` Arbiter event when the user clicks an item, but I observe the event never arrives at the game state subsystem."*

**Phase 1.3 git log:** `git log -p -- Modules/Gameplay/Inventory/InventoryModule.cpp` shows a recent commit refactoring the event publication into a helper method. Strong prior hypothesis.

**Round 1 placement:**
- `start` — `InventoryModule::ApplyItem` entry.
- `mid` — just before the helper call `PublishApplied(Item)` (structural boundary: interface crossing into the publish path).
- `end` — inside the subscriber on the game state side.

`Logs/Claude.log`:
```
InventoryModule::ApplyItem entry Item=Potion
InventoryModule::ApplyItem about to call PublishApplied Item=Potion
```

`end` is missing. Round-1 conclusion: bug is in `[mid, end]` — between the helper call and the subscriber. Retain second half; remove the `start` trace; pick a new midpoint inside `PublishApplied`.

**Round 2 placement:**
- `start` — now inside `PublishApplied` at entry.
- `mid` — just before the `Arbiter::Publish<ItemApplied>(...)` call.
- `end` — unchanged, in the subscriber.

`Logs/Claude.log`:
```
PublishApplied entry Item=Potion
```

`mid` is missing — the code never reaches the `Arbiter::Publish` call. Reading the five lines between `start` and `mid` reveals an early return guarding on `m_bEnabled`, which the refactor left uninitialized. Root cause located. Fix, re-verify, run Phase 5 cleanup audit, report.

## Related Skills and Agents

- **Crashes, segfaults, or any bug with a usable stack trace** → `invoke-debugger-agent` (GDB/LLDB, hardware watchpoints, core dumps).
- **Concurrency-related bugs, or Heisenbugs traces can't catch** → `invoke-concurrency-agent` (TSAN, memory-ordering analysis, lock-free verification).
- **Memory corruption, leaks, or use-after-free** → `invoke-memory-agent` (ASan/MSan/LSan, Valgrind).
- **Overall debugging methodology** (root-cause investigation, hypothesis-driven approach) → `superpowers:systematic-debugging`. This skill is the Phoenix-specific implementation of its "gather evidence" phase.
