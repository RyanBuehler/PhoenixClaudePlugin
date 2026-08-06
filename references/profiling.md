# Profiling — Phoenix Rules

Authoritative rules for **measurement**: whether a system's cost can be seen, and whether
the instrumentation that shows it is placed, named, and priced correctly.

This is about *visibility of cost*. Making the cost smaller is
[`optimization.md`](optimization.md); the two are read together, measurement first.

Rules carry stable IDs (`P1`…`P21`).

## The two instruments

| | `ScopedProfile` | `Logging::ScopedTimer` |
|---|---|---|
| Records | begin/end events to VigilAgent | one log line on destruction |
| Cost when off | zero — collapses to an empty struct | none; it always logs |
| Names by | `Label` (interned, compile-time) | `string_view` |
| Use for | recurring work — a pass, a tick, a per-item step | one-shot work — startup, an asset load, a build step |

`ScopedProfile` is the default. `ScopedTimer` writes to a log file on every destruction,
so it is a one-shot instrument wearing an RAII shape.

## §1 Coverage — can the cost be seen at all

**P1** — **A subsystem's tick entry point carries a scope.** An unprofiled subsystem is
invisible in a capture, and invisible cost is never the cost anyone fixes.

**P2** — Instrument a boundary you can act on. A scope around code you cannot change
measures something you cannot fix.

**P3** — Scope boundaries match a unit of work a reader would name: a pass, a subsystem
tick, a load, a compile. Not every function.

**P4** — At most one scope per function. Two scopes in one function is the function
telling you it does two things.

## §2 Placement — is the number attributed correctly

**P5** — A scope must not span a blocking wait — a join, a lock acquisition, a fence —
unless the wait *is* what is being measured. Otherwise the number lands on the wrong work.

**P6** — Nested scopes double-count by design: a parent's time already includes its
children. Nest deliberately, and never sum siblings and parent together.

**P7** — Do not scope the constructor or destructor of a small, frequently-created object.
The instrument costs more than the thing it measures.

**P8** — **No logging inside a measured region.** Scribe writes to disk; a `Trace` in the
middle of a timed scope is measuring Scribe.

## §3 Naming

**P9** — Scope names are compile-time `Label` literals. Never build a scope name at
runtime — it defeats interning and makes captures uncomparable across runs.

**P10** — Name the work, not the symbol. `"Shadow pass"` survives the rename that
`"RenderShadowsImpl"` does not.

**P11** — Names are unique. Two scopes sharing a name merge into one row in the capture,
and the merged row is a lie.

## §4 Hygiene

**P12** — Never hand-roll a `steady_clock::now()` pair. `ScopedProfile` and `ScopedTimer`
exist; a manual pair drifts on early return and skips the exception-free unwind path.

**P13** — No `#ifdef` gating around instrumentation. `ScopedProfile` is already inert when
profiling is off, and preprocessor guards in shared code are forbidden by the style guide.

**P14** — **A temporary probe never lands in a commit.** A scope added to answer one
question is a debugging tool, like a breakpoint.

**P15** — `ScopedTimer` never appears in a per-frame or per-sample path. It logs on every
destruction; at frame rate that is a flood, and the flood changes the measurement.

## §5 Reporting a number

**P16** — Any measurement written to a log obeys `logging.md` — units (L8), float
precision (L14), no leading interpolation (L23).

**P17** — A number carries its basis: per frame, total, mean, or worst. A bare duration
with no basis cannot be compared to anything.

**P18** — **Never compare timings across build configurations.** Debug numbers do not
predict Release ones, and a Debug-build slowdown is not a defect to optimize.

**P19** — A claim that something is faster carries a before/after measurement. Without
one it is a hypothesis.

**P20** — Measure the same thing twice before believing it. A single sample of a
frame-timed system measures scheduler noise as much as work.

**P21** — When a cost is allocation-driven or call-count-driven, count the allocations or
the calls. Wall time alone hides which of the two moved.
