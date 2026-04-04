# Trace Placement Heuristics

Detailed guidance for Phase 2 of `phoe:trace-debug`, loaded when the "three traces per round — start, structural midpoint, end" rule needs sharper discrimination about *where* within a function or subsystem to place them.

## High-value placement sites, in priority order

These are the sites where bugs most often hide. When picking a midpoint or adding traces to an already-narrowed region, prefer these in order:

1. **Function entry.** Always worth a trace — it proves control flow reached the function at all. Most "it doesn't work" bugs turn out to be "it never ran."

2. **Branch predicates — log the value, not just the path.** Place the trace *before* the branch and log the predicate's value, not the branch that was taken. `LogF("X=%d about to branch", X)` tells you both which path and why; a trace inside the `if` body tells you only the path.

3. **Loop boundaries and invariants.**
   - Loop entry with the iteration count (or container size).
   - Inside the first iteration (confirm the loop body runs at all).
   - After the loop with the final accumulator/collection state.
   - If a specific iteration is suspect, a guarded trace: `if (Index == SuspectIndex) LogF(...)`.

4. **State-mutating assignments to the variables the bug cares about.** Trace immediately before and after any assignment to a member variable, flag, or container entry involved in your hypothesis. The "before" trace tells you the input; the "after" trace tells you whether the write happened.

5. **Interface boundaries — trace on both sides.**
   - Subsystem calls: `Subsystem::Get<IFoo>()->Bar(x)` — trace before (with `x`) and immediately inside `Bar` (confirm arrival and value agreement).
   - Virtual dispatch: trace at the call site and inside the concrete override.
   - Callback invocations: trace at the invoke site and inside the callback.

6. **Arbiter event boundaries.** Trace just before `Arbiter::Publish<Event>(...)` and at the first line of every subscriber's handler. Event-bus bugs are the #1 case where "the code looks right" — either the event isn't published, the subscriber isn't registered, or the payload is wrong.

7. **Error and early-return paths — especially the ones you "know" aren't taken.** The early return you dismissed as "that can't happen here" is disproportionately likely to be the bug. Put a trace on it.

8. **Lock acquire/release pairs.** Trace on lock acquisition (with the resource being protected) and on release. Never inside the critical section — that defeats the point of the lock and creates Heisenbug risk.

9. **RAII destructor entry** for types whose lifetime is part of your hypothesis. If you think the bug is "object destroyed at the wrong time," a trace in the destructor with `this` and a timestamp is decisive.

10. **Resource allocation / deallocation pairs.** Allocation site with the size or count; deallocation site with the same. Imbalances pop out immediately.

## Low-value sites — avoid

- **Tight numerical inner loops.** The log floods and the formatting overhead may mask the bug (Heisenbug risk). If you must trace inside one, use a guarded counter and log only the summary outside the loop.
- **Constructors or destructors of value types used in hot containers** (e.g., an `std::vector<MyVec3>`). Each element triggers a trace, and the log is unreadable.
- **Templates you cannot inspect the instantiation of.** A trace inside a template may fire more or fewer times than you expect; the noise-to-signal ratio is bad. Trace at the call site of the instantiated template instead.
- **`operator<<` or stream formatters.** Recursion risk if Scribe itself uses the operator.
- **Phoenix tick-rate-sensitive code** (the Engine main tick, input polling, Aurora frame setup). Every trace runs every frame; the log becomes a firehose.

## What to put in the format string

Prefer information density over cleverness:

- **Values over types.** `Count=%d` beats `"entered function"`.
- **Enum names over ints.** If you have a debug stringifier for an enum, use it. Otherwise log the int AND the line so you can correlate.
- **Non-null pointer checks over addresses.** `Ptr=%s` with `(Ptr ? "set" : "null")` is more useful than `Ptr=0x7ffd1234`.
- **Loop counts over pointer arithmetic.** `Size=%zu Index=%zu` beats `(End - Begin)`.
- **Collection summaries, not dumps.** First element and last element plus size, not every element.

## Phoenix-specific placement tips

- **`Subsystem::Get<>()` call sites** are high-value midpoints. The lookup can return `nullptr` if the module isn't registered in this application's `*Description.json`, and the bug may be "the module isn't loaded at all." Trace the return value and branch on it.
- **`Arbiter` event bus.** Publish sites and subscriber registration are the two highest-prior spots. A missing subscriber registration is silent — there is no warning when you publish to nothing — and only a trace will reveal it.
- **`Engine::Tick` phases.** The tick is divided into ordered phases (PreTick, Tick, PostTick, Render). If your bug crosses phases, trace at each phase boundary with the state you care about. Bugs here usually turn out to be "I mutated X in PostTick but read it in PreTick of the next frame."
- **Platform liaisons** (`LinuxPane`, `LinuxInput`, `WindowsPane`, etc.). Platform-specific bugs almost always live at the liaison boundary — trace on the inbound call from the platform layer and on the outbound call to the module that consumes the event.
- **Headless vs. windowed divergence.** If a bug only repros in one, trace the same code path in both and diff the logs. The first differing line is the divergence point.

## When none of the above is obviously right

Pick the nearest structural boundary and go. Judgment beats analysis paralysis — a mis-placed trace still produces data, and the bisection table in `SKILL.md` Phase 3 tells you what to do next regardless of where you placed it. If after two rounds you've learned nothing, the problem is usually Phase 1 (wrong region, non-determinism) rather than placement.
