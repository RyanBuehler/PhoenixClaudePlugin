# Audit: optimization

Waste — work the program does that it does not need to do. Whether that waste is *visible*
is `audits/profiling.md`, and it comes first.

## Rules

Read [`references/optimization.md`](../../../references/optimization.md) (`O1`…`O24`).
O1 defers to `references/profiling.md` P19 for the measurement requirement.

## The standing caveat

This is the one audit type that can make code worse. Every finding here is a hypothesis
about cost, and a hypothesis applied without a measurement is how a codebase acquires
unreadable code that is no faster.

**Default to `--dry-run` reasoning even when fixing.** Report the waste, name the cheap
fix, and let a measurement decide. The exceptions are the findings that cost nothing to
take: O7, O11, O14, O23.

## Finding the sites

Start from the hot paths, not from the top of the file. A finding in code that runs once
at startup is not a finding.

```bash
# Loop bodies and per-frame entry points are the only places most of these matter
grep -nE '\b(for|while)\s*\(|\b(Tick|Update|Render|Process|Step)\s*\(' <file>
```

## Detection

| Rule | Spot it by |
|---|---|
| O2 | A nested loop over the same container; a linear scan inside a loop |
| O4 | Two functions with near-identical bodies, one labeled "fast" |
| O5 | A bounds or validity check removed with a comment claiming speed |
| O6 | `new`, `make_shared`, `vector`/`string` construction inside a loop body |
| O7 | `push_back`/`emplace_back` in a loop with no preceding `reserve` |
| O8 | A container built, iterated once, and discarded |
| O9 | `string(…)` or `.ToString()` built solely to feed a comparison |
| O10 | A non-trivial parameter taken by value that is only read |
| O11 | `push_back(T{…})`; a copy where the source is dead afterward |
| O12 | `shared_ptr<T>` taken by value for a single method call |
| O13 | An out-parameter with a comment about avoiding a copy |
| O14 | `find` followed by `operator[]` or `at` on the same key |
| O15 | A call inside a loop whose arguments never change; an `if` on a loop-invariant condition |
| O16 | A virtual call in an inner loop where the type is fixed per call |
| O17 | A cached member with no visible invalidation point |
| O18/O19 | `list`, `map`, or `set` where a `vector` or flat map would serve |
| O20 | A cold field — a name, a debug string, a rarely-read flag — inside a per-frame struct |
| O22 | A hand-inlined or macro-ized version of an existing abstraction |
| O23 | A local or member that is never reassigned and is not `const` |
| O24 | A thread spawned for work with no measured contention |

## Severity

| | Rules |
|---|---|
| **Critical** | O5 (a check removed for speed is a correctness bug wearing a performance costume), O4, O17 |
| **Warning** | O1, O2, O3, O6, O8, O9, O12, O14, O16, O20, O24 |
| **Nit** | O7, O10, O11, O13, O15, O18, O19, O21, O22, O23 |

Note the shape: the Critical findings are the ones where an *optimization already applied*
introduced a bug. The waste itself is rarely worse than Warning.

## Fix buckets

| | Rules |
|---|---|
| **Mechanical** | O7 (add `reserve`), O11 (`emplace_back`, `Move` at last use), O14 (keep the iterator), O23 (add `const`) |
| **Judgment** | O6, O8, O9, O10, O12, O13, O15, O16, O21, O22 |
| **Report-only** | O2, O4, O5, O17, O18, O19, O20, O24 — every one is a redesign |

O2 is report-only no matter how obvious the better algorithm looks. Changing complexity
changes behavior under inputs nobody has tested.

## False positives

- **Cold code is exempt from all of it.** Startup, teardown, editor tooling, and asset
  import run once; an allocation there costs nothing worth a diff.
- Clarity beats a nit-level win. If the `reserve` or the `emplace_back` makes the line
  harder to read, leave it and say so.
- O10 does not apply to a sink parameter — taking by value and `Move`-ing into place is
  the correct idiom, not a copy.
- O18/O19 do not apply where reference or iterator stability is required. Check for stored
  pointers into the container before recommending contiguous storage.
- An `O(n²)` loop over a bounded, small `n` is not a defect. Find the bound before
  reporting.
