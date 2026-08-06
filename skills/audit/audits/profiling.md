# Audit: profiling

Whether a system's cost can be seen, and whether the number means what it appears to mean.
Making the cost smaller is `audits/optimization.md`.

## Rules

Read [`references/profiling.md`](../../../references/profiling.md) (`P1`…`P21`). P16 defers
to `references/logging.md` (L8, L14, L23) for any measurement written to a log; read that
if the target logs timings.

## Finding the sites

```bash
grep -nE 'ScopedProfile|ScopedTimer' <file>

# P12 — hand-rolled timing that should be a scope type
grep -nE 'steady_clock::now|high_resolution_clock|QueryPerformanceCounter|clock_gettime' <file>
```

Coverage findings are the inverse: look for the **absence** of a scope at a tick entry
point.

```bash
grep -nE '\b(Tick|Update|Render|Execute|Step)\s*\(' <file>
```

## Detection

| Rule | Spot it by |
|---|---|
| P1 | A subsystem tick entry point with no `ScopedProfile` |
| P3 | A scope named for a symbol rather than a unit of work |
| P4 | Two `ScopedProfile` declarations in one function body |
| P5 | A scope whose region contains a `join`, `lock`, `wait`, or fence |
| P6 | A nested scope whose parent already covers the same work |
| P7 | A scope in the constructor or destructor of a small value type |
| P8 | A `Trace`/`Log` call inside a scope's region |
| P9 | A scope name built with `format`, concatenation, or a runtime variable |
| P10 | A scope name matching a function name, especially one ending `Impl` |
| P11 | The same scope name at two sites — sweep the target with `sort \| uniq -d` |
| P12 | The hand-rolled clock sweep above |
| P13 | `#ifdef` or `#if` wrapped around instrumentation |
| P14 | A scope with a probe-shaped name — `test`, `tmp`, `here`, `x` |
| P15 | `ScopedTimer` in a function named `Tick`/`Update`/`Render`, or inside a loop |
| P16/P17 | A logged duration with no unit, no precision, or no basis |

## Severity

| | Rules |
|---|---|
| **Critical** | P15 (a `ScopedTimer` at frame rate floods the log and corrupts its own measurement), P14 (a committed probe) |
| **Warning** | P1, P2, P5, P6, P8, P9, P11, P12, P13, P18, P19 |
| **Nit** | P3, P4, P7, P10, P16, P17 |

P5, P6, P8, and P11 are Warning rather than Nit for one shared reason: each produces a
number that is *wrong* rather than missing, and a wrong number sends the next optimization
at the wrong target.

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | P13 (drop the guard — `ScopedProfile` is already inert), P14 (delete the probe), P10 (rename to the work) |
| **Judgment** | P3, P4, P9, P11, P15, P16, P17 — each needs a name or a unit chosen |
| **Report-only** | P1, P2, P5, P6, P7, P12, P18–P21 |

Adding a missing scope (P1) is report-only, not a fix to apply. Where instrumentation
belongs is a design question, and a scope in the wrong place is worse than none — it
produces a confident wrong number.

## False positives

- **`Engine/Core/Public/Profiling/` and `Logging/ScopedTimer.cppm` are the owners.** They
  legitimately hand-roll clocks and manage scope state; exempt them from P12.
- A `ScopedTimer` in a startup, load, or build path is correct usage, not P15. Check
  whether the enclosing function runs once before reporting.
- A scope that deliberately spans a wait — measuring stall time — is P5-exempt when a
  comment says so. That comment is the difference between a measurement and a mistake.
- Absence of instrumentation in a cold path is not a finding. P1 asks for coverage at tick
  entry points, not everywhere.
