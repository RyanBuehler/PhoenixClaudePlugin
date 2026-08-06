# Optimization — Phoenix Rules

Authoritative rules for **waste**: work the program does that it does not need to do.

Whether that waste is visible is [`profiling.md`](profiling.md), and it comes first — an
optimization without a measurement is a guess with a maintenance bill. Rules carry stable
IDs (`O1`…`O24`).

## §1 Before touching anything

**O1** — **Measure first.** No change lands as an optimization without a before/after
number (`profiling.md` P19).

**O2** — **Algorithm before constant factor.** An O(n²) loop rewritten as O(n log n) beats
every micro-rewrite of its body, and it beats them at every input size that matters.

**O3** — **Behavior stays identical.** If observable results change, it is a redesign and
needs to be reviewed as one.

**O4** — **Never optimize by duplicating.** A fast path that shadows a slow path drifts
from it, and the drift is a bug that only appears under load.

**O5** — Do not remove a bounds or validity check for speed. Restructure so the check
happens once outside the loop instead.

## §2 Allocation

**O6** — **No allocation in a per-frame or per-sample path.** Preallocate, reserve, or
draw from a pool.

**O7** — `reserve()` before a loop that appends a known or bounded count.

**O8** — No temporary container built to be iterated once and discarded. Iterate the
source, or take a view.

**O9** — No `string` built for the purpose of comparing it. Compare `string_view`, and
compare `Label` to `Label` without round-tripping through text.

## §3 Copies and moves

**O10** — Pass by `const&`, `string_view`, or `span`. Take by value only when the function
sinks the argument, and then `Move` it into place.

**O11** — `Move` at the last use rather than copying into a container. `emplace_back` over
`push_back(T{…})`.

**O12** — Do not copy a `shared_ptr` to call one method on the pointee. Pass a reference;
the refcount bump is an atomic and it is contended.

**O13** — Return by value and let RVO do its work. An out-parameter "for speed" costs
clarity and buys nothing.

## §4 Redundant work

**O14** — **One lookup, not two.** `find` followed by `operator[]` hashes twice; keep the
iterator, or use `try_emplace`.

**O15** — Hoist loop-invariant work out of the loop — including the invariant *branch*.
A condition that cannot change inside the loop belongs outside it, as two loops or a
template parameter.

**O16** — Resolve virtual dispatch once outside an inner loop rather than per iteration.

**O17** — Cache a recomputed value only with a measured win and one clear invalidation
point. A cache without an obvious invalidation is a correctness bug in waiting.

## §5 Layout and container choice

**O18** — Contiguous storage by default. Node-based containers only when reference or
iterator stability is genuinely required.

**O19** — For small, read-mostly maps prefer a flat/sorted representation over a hashed
one — fewer indirections, better locality.

**O20** — Keep hot fields together. Cold data interleaved into a struct walked every frame
costs a cache line per element forever.

**O21** — Do not hand-tune alignment or padding by guess. Align to a measurement or to a
documented hardware requirement, not to a hunch.

## §6 Restraint

**O22** — **Zero-cost abstractions stay.** Do not hand-inline, flatten, or macro-ize for
speed without a number showing the abstraction was the cost.

**O23** — `const` and `constexpr` wherever they are true. They enable optimization and
cost nothing to write.

**O24** — **Threading is not a first resort.** Parallelism is an optimization that bills
you in correctness; exhaust the single-threaded waste first, and when you do reach for
concurrency it goes through Arbiter.
