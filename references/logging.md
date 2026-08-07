# Logging — Phoenix Rules

Authoritative rules for **log message content, level, and form**. Channel mechanics
(`<Module>Log.h`, file-scope `using namespace`) are in
[`style-guide.md`](style-guide.md) §Namespaces; the "inspect the error, log on the
unexpected branch" rule is §Error Handling. This document does not restate them.

Rules carry stable IDs (`L1`…`L32`). Cite the ID in reviews and audit findings.

## The line you are writing into

Scribe emits one line per event:

```
<timestamp> [Category][Level]: <your message>
```

Categories get their own file (`Logs/<Category>.log`), so the category is already
established by the time anyone reads the text.

Scribe adds **nothing else**. There is no thread ID and no function name;
`bLogSourceFile` is off by default, and `bLogTimestamp` / `bLogCategoryName` can both
be turned off. Two consequences drive most rules below: **the message carries its own
identity**, and **it may not assume the line above it is related**.

## §1 Level

| Level | Use when | Must state | Never |
|---|---|---|---|
| `Fatal` | The process is about to terminate | What was unrecoverable | …and then continue |
| `Error` | Requested work did not happen | Subject, cause, consequence | For something the caller handles |
| `Warn` | Continued, but degraded or an input was refused | What was refused, what follows | For a condition normal flow expects |
| `Log` | Notable event, at a rate a human can read | The state now in effect | Routine success |
| `Trace` | Systems tracing; suppressed by default | State transitions | Control-flow narration |

**L1** — Level reflects consequence to the *program*, not your interest while debugging.
Wanting to see something is what `LogLevel=Trace` plus `EnabledTraceCategories` is for.

**L2** — One failure, one report. Log where you can name the consequence; propagate
everywhere else. A failure reported at every layer of the stack is noise that hides the
one line that mattered.

**L3** — Success is the absence of noise. `Log` a success only for a one-shot milestone
— device selected, configuration resolved, subsystem online.

## §2 Content

**L4** — **Name the subject.** Include the identity a reader can grep for or search the
code with: a `Label`, a path, `slot {}, generation {}`.

> ✗ `Warn("Failed to register")`
> ✓ `Warn("Failed to register '{}': {}", Name, Error)`

**L5** — **State the consequence.** What will not happen now is what makes a line
triageable.

> ✗ `Error("The mix pipeline refused its configuration")`
> ✓ `Error("The mix pipeline refused its configuration; audio is inert")`

**L6** — **Carry the underlying error text.** Never collapse an `expected` error into
your own generic sentence — the inner message is the part that identifies the cause.

**L7** — **Add nothing the line already carries.** No category prefix (`[Scribe] …`), no
level word (`ERROR: …`), no timestamp.

**L8** — **Units on every number**, and bounds where a number is one of a pair:
`{} ms`, `{} bytes`, `gain {} over {} ms`, `slot {}, generation {}`.

**L9** — **No addresses or pointers.** They are nondeterministic and unactionable; log
the identity of the thing instead.

## §3 Form

**L10** — One event, one line. No embedded newlines. For a multi-row dump, repeat a
stable prefix on every line — concurrent emitters break adjacency, so a continuation
line that reads as a fragment can surface alone.

**L11** — **Never a terminal period.** A message is one clause and it stops.

> ✗ `Trace("Initialized.")`
> ✓ `Trace("Initialized")`

**L12** — Quote interpolated identity strings, leave numbers bare:
`Event '{}' was not posted: {}`.

**L13** — A message carrying more than one thought joins them with a separator rather
than splitting into sentences. Most messages need none of these.

| Separator | Introduces | Example |
|---|---|---|
| `:` | the cause | `Streaming '{}' could not start: {}` |
| `;` | the consequence | `The mix pipeline refused its configuration; audio is inert` |
| `-` | an instruction | `Trace category '{}' is unknown - add it to EnabledTraceCategories` |

**L14** — Floats get precision (`{:.2f}`), never a bare `{}`.

**L15** — The message is a compile-time literal with holes. Do not `format()` into a
string in order to call the preformatted overload — that overload exists for genuinely
runtime text.

**L16** — No ANSI escapes, emoji, banners, or box-drawing. The sink owns presentation.

## §4 Voice

**L17** — American English, sentence case. No exclamation marks, no ALL-CAPS emphasis.

**L18** — Name the actor and what it did. Passive voice hides who to go look at.

> ✗ `Warn("The voice could not be stopped")`
> ✓ `Warn("The mix pipeline refused to stop the test tone's voice")`

**L19** — Present tense for what is, past tense for what happened. No future tense
("will now retry") — log the retry when it happens.

**L20** — No first person, no addressing the reader, no apologies. A log is a record,
not a conversation.

**L21** — No filler ellipses and no filler words. `"Initialized..."` → `"Initialized"`.

**L22** — Invariant text stays under roughly 100 characters. If you need more, you need
another interpolated value, not a longer sentence.

## §5 Machine readability

Logs are read by agents and by CI tails as often as by people. These rules are what make
a line usable to a reader who has no surrounding context.

**L23** — **Invariant text leads.** A message that starts with `{}` cannot be grepped
back to its call site. The first move of anyone triaging is `grep -r "<literal>"`; that
grep must land.

> ✗ `Trace("{} ({})", Name, State)`
> ✓ `Trace("Subsystem '{}' entered {}", Name, State)`

**L24** — **Unique per call site.** Two call sites sharing one invariant string make the
grep in L23 ambiguous. Distinguish near-siblings by naming what differs.

**L25** — **Self-contained.** A reader sees slices, not whole files. Subject, what
happened, and consequence belong on the one line.

**L26** — **Stable across runs.** No addresses, no in-text timestamps, no loop counters
in the invariant part. Diffing two runs should surface only real differences.

**L27** — **Right category.** The category is the reader's filter. A trace emitted to
`General` from a module that owns a channel cannot be isolated by
`EnabledTraceCategories`.

**L28** — **No secrets, credentials, tokens, or user home paths.** Log lines get pasted
into issues, PRs, and agent contexts.

## §6 Mechanics and cost

**L29** — Go through the module's channel. Module code never calls `Scribe::` directly.

**L30** — No `printf`, `cout`, `cerr`, or `fprintf` in engine code.

**L31** — No unthrottled logging in a per-frame or per-sample path. Use `ThrottledTrace`
/ `ThrottledWarn` with an explicit interval.

**L32** — **Trace arguments are evaluated even when the trace is suppressed.** `Log.inl`
gates nothing at the call site, so building a string, joining a container, or calling
`ToString()` for a `Trace` costs that work in every shipping build. Pass cheap values,
or guard the whole site with `if constexpr (Build::IsDebugBuild)`.

> ✗ `Trace("Plan: {}", Join(Levels, ", "))`
> ✓ `if constexpr (Build::IsDebugBuild) { Trace("Plan: {}", Join(Levels, ", ")); }`
