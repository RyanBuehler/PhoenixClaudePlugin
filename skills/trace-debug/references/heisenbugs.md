# Heisenbugs — When Your Traces Are the Problem

Detailed reference for the Heisenbug Handling section of `phoe:trace-debug`, loaded when traces cause the bug to vanish, shift, or change shape. A Heisenbug is a first-class finding: "traces mask this bug" narrows the root-cause category more than you might expect, so capture it in your report even when you escalate away from trace-based debugging.

## Taxonomy of trace-induced vanishings

Five distinct mechanisms cause traces to hide bugs. Diagnosing which one you're in determines the mitigation.

### 1. Ordering imposition

`Scribe::LogF` takes an internal mutex, formats the message, and writes to the log buffer. That mutex, and the side effects around it, impose a happens-before edge that may synchronize a race the original code didn't have. A benign-looking trace can turn a racy read into an ordered one for the duration of the experiment.

**Signature:** The bug exists in multithreaded code. It appears and disappears depending on which thread holds a trace. Single-threaded tests pass.

**Mitigation:** Remove all traces from the suspect hot path one at a time; the last one whose removal brings the bug back is imposing the ordering. The bug lives in that region. Then escalate to `invoke-concurrency-agent`.

### 2. Optimization defeat

In Release builds the compiler applies NRVO, dead-code elimination, loop unrolling, and aggressive inlining. When you add a trace that reads a variable, you create a use that the compiler must honor — suddenly a variable that had been elided now exists, a side effect that had been DCE'd now runs, a return value that had been NRVO'd now gets copied. The *unoptimized* behavior is "correct" and the *optimized* behavior was the bug.

**Signature:** The bug only reproduces in Release. Adding ANY trace in the suspect function makes it vanish. Switching to Debug also makes it vanish.

**Mitigation:** Compile the specific translation unit with `-O0 -g` (or adjust the target's `CMAKE_CXX_FLAGS` for a one-off repro) and re-run. If the bug still vanishes at `-O0`, it's not this category. If it persists at `-O0` and vanishes at `-O2`, you've found a compiler-observed side-effect issue — often an uninitialized read, a strict-aliasing violation, or UB that the optimizer is exploiting. Hand off to `invoke-debugger-agent` with the finding.

### 3. Cache and prefetcher disturbance

A trace call added to a hot path introduces instruction cache pressure, disrupts the branch predictor, and may push the prefetcher off the correct stride. Timing-sensitive races — the kind that depend on "thread A wins by 20 cycles" — collapse when you perturb the timing even slightly.

**Signature:** The bug exists in a tight hot loop or a time-sensitive code path (input handling, audio callback, tick synchronization). Traces anywhere near the hot path make it vanish, even traces outside the loop body.

**Mitigation:** Move traces progressively further from the suspect region until the bug returns. The last position where the bug returns tells you the cache footprint matters — this is almost certainly a concurrency/timing issue. Escalate to `invoke-concurrency-agent`.

### 4. Cache-line coincidence (false-sharing-style)

A trace statement may write to a local variable that happens to share a cache line with the racing variable the bug depends on. The write invalidates the line, and the race's racing write now appears to "see" a consistent value because the cache coherence protocol forced a sync. Particularly insidious because it depends on compiler layout decisions.

**Signature:** Similar to category 1 (concurrency-related), but removing the trace from any function — even an unrelated one — may change the behavior because any edit shifts stack layout.

**Mitigation:** Very hard to diagnose from logs alone. If you suspect this, stop bisecting and escalate to `invoke-concurrency-agent` with a note that stack layout appears to matter.

### 5. Initialization ordering

`Scribe::LogF("Claude"_L, ...)` may trigger lazy initialization of the `"Claude"` category on first call. That initialization allocates, takes locks in the Scribe subsystem, and may pull in other lazy singletons. If your bug depends on *when* something initializes, the first trace you place moves the init point and changes the bug.

**Signature:** The bug happens during startup or teardown. Adding the *first* trace changes behavior; adding more doesn't change much beyond that.

**Mitigation:** Force Scribe initialization explicitly at the top of `main()` before any suspect code runs, so the first trace isn't the trigger. Alternatively, place a throw-away trace very early (outside your suspect region) to absorb the init cost, then trace normally. If the bug persists, init ordering isn't the cause.

## Diagnostic procedure

When you suspect a Heisenbug, work through these in order:

1. **Confirm it's actually a Heisenbug** via dual-run: same binary, same repro, WITH traces vs. WITHOUT. If both fail or both pass, it's not a Heisenbug — it's a Phase 1 reproducibility failure.

2. **Reduce overhead progressively.** Strip format-string arguments (log a bare int), move to scope boundaries, use lightweight atomic counters instead of text. If the bug returns at any step, the overhead of the removed piece was the mask.

3. **Move traces outward.** If overhead reduction doesn't help, move each trace one scope outward (to the caller, then the caller's caller) until the bug reappears. The last-moved trace's previous position is inside the disturbance zone.

4. **Try Debug build.** If the bug is Release-only and Debug makes it vanish, you're in category 2 (optimization defeat) — escalate with that finding.

5. **Give up on traces, escalate.** When reductions and moves exhaust themselves, you are using the wrong tool. Hand off to `invoke-debugger-agent` (hardware watchpoints catch what traces can't) or `invoke-concurrency-agent` (TSAN, memory ordering). The fact that traces mask the bug IS the finding — include it verbatim in your handoff.

## Report hygiene

If a Heisenbug terminates your bisection, your report to the user must state:

- Which category (1–5) best matches the signature.
- Which mitigations you tried and what each revealed.
- The suspect region you narrowed to before traces started masking.
- Which agent you're recommending the user escalate to.

"Traces mask this bug" is not a failure — it's a concrete technical finding that rules out large classes of root causes and points at others. Own it in the report.
