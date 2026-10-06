---
name: vigil
description: Profile a Phoenix Editor interaction with Vigil, from launch to a parsed finding, with no window touched.
---

Profile one interaction in the Editor end to end:
1. Configure profiling.
2. Launch an Editor.
3. Enable a trace scope category.
4. Drive a repro through the console pipe.
5. Capture.
6. Stop.
7. Query and assert.

`vigil_loop.py run` is the whole loop. It needs no window and no manual step, and it prints one JSON
summary whose `failure` names what went wrong.

**The loop launches its own Editor. It cannot attach to one that is already running.** No agent can
open a capture at run time: the console pipe refuses `vigil.capture.start` and `vigil.capture.stop`.
A capture opened late would also lack the thread names and label definitions the engine already
sent. So the loop names the capture file in `Vigil.cfg` before launch, and the capture opens with the
engine.

The human version of this loop, step by step, is `Docs/Vigil_DD.md` section 6.4 in the repository.

## Arguments

- **`<interaction>`**: what to profile, as console lines the Editor runs (the repro).
- **`<category>`**: the trace scope category that covers it (default: the owning module's).
- **`<budget>`** *(optional)*: `SCOPE=MS` per frame, which the loop asserts over the repro's frames.

## 1. Build the two binaries

Build through `/phoe:build`, which owns the procedure. The loop needs these two binaries:

| Binary | Linux profile | Windows profile |
|---|---|---|
| Editor with VigilAgent linked | `editor-profiling` | `editor-profiling-windows` |
| `vigil`, without the viewer | `vigil-cli` | `vigil-cli-windows` |

Which Editor profiles link VigilAgent:
- **Linux**: `editor`, `editor-headless` and `editor-profiling` all link it.
- **Windows**: only `editor-profiling-windows` links it; `editor-windows` leaves it out.
- An Editor without VigilAgent fails as `profiling_inactive`, or as `config_unwritten` when it has no
  `Vigil.cfg` yet.

Take each binary's path from the build's `--json` result (`output_path`), not from a guess. Under
`Applications/Forge/.forge/<profile>/bin/` they are `editor`/`editor.exe` and `vigil`/`vigil.exe`.

## 2. Pick the category and the repro

- **The category**: the module's own name, from its `*Profile.h` (`Aurora`, `Prism`, `Mosaic`,
  `Soulforge`, ...). An unknown name fails as `unknown_category`, and the engine's answer lists every
  registered category, so a wrong guess costs one run.
- **The repro**: console lines that are open to agents.
  - The loop itself uses four of them: `vigil.trace`, `quit`, `help` and `aurora.screenshot`.
  - `help` lists every registered command, including the ones closed to agents, so it is no guide to
    what may run. A `refused` failure means the command is closed to agents.
  - Python does not run over the console pipe. A repro that needs a binding goes through Dispatch,
    which a profiling build does not carry.
  - In a console line, `;` separates commands and `\` escapes inside quotes. Quote a path argument and
    write it with forward slashes.
- **Asynchronous repros**: name a file that appears when the repro is done (`--repro-signal`), and
  one that appears when it fails (`--repro-error`). `aurora.screenshot` writes `.last-capture` and
  `.capture-error` respectively.
- **The assertion**:
  - `--frame-budget=SCOPE=MS` fails on the worst frame and names it.
  - `--budget` averages across frames.
  - `--max-dropped-pulses=N` bounds dropped pulses.
  - Each is held over the repro's frames.
  - With none of them, `vigil check` does not run. The loop still fails as `gaps` when the monitor
    flagged a gap.

## 3. Run the loop

**Give the run a 600000 ms tool timeout, or start it with `run_in_background`.** Start-up, repro,
shutdown and queries can together outlast the default 120 s. Killing `python` from outside then
leaves its Editor and monitor running. The script stops them itself on Ctrl+C and SIGTERM, but
nothing can catch a hard kill.

Linux (bash):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vigil_loop.py run \
  --editor "$EDITOR_BIN" --vigil "$VIGIL_BIN" --work /tmp/vigil-run \
  --category Aurora \
  --repro 'aurora.screenshot output_directory="/tmp/vigil-run/shots"' \
  --repro-signal /tmp/vigil-run/shots/.last-capture \
  --repro-error /tmp/vigil-run/shots/.capture-error \
  --frame-budget PNG::Encode=50
```

Windows (PowerShell): the same flags. Use `python`, not `python3`, and Windows paths. The console
pipe defaults to a per-run named pipe (`\\.\pipe\phoenix-vigil-<pid>`), because a Windows console
pipe must be a named pipe.

```powershell
python ${CLAUDE_PLUGIN_ROOT}/scripts/vigil_loop.py run `
  --editor $EditorExe --vigil $VigilExe --work C:\tmp\vigil-run `
  --category Aurora `
  --repro 'aurora.screenshot output_directory="C:/tmp/vigil-run/shots"' `
  --repro-signal C:\tmp\vigil-run\shots\.last-capture `
  --repro-error C:\tmp\vigil-run\shots\.capture-error `
  --frame-budget PNG::Encode=50
```

How the Editor is started:
- The loop puts the build's `lib/` (beside `bin/`) on the Editor's library path. Windows needs this for
  the Editor's DLLs.
- On Linux with no display, the loop starts the Editor under `xvfb-run -a` itself. `--launch-prefix ""`
  turns that off, and another prefix replaces it.
- On Linux, the Editor runs in a process group of its own, so a kill also reaches Xvfb.

What the run changes, and what it puts back:
- **`Configuration/Vigil.cfg` beside the Editor.** The loop turns profiling on and names the capture
  file. Once the Editor exits it puts the file back as it found it, removing it if there was none.
  This happens on every failure path too, so a later launch neither profiles nor truncates the
  capture; the summary says `config_restored`.
- **A `Vigil.cfg` that is a parcel the script cannot read** is refused as `config_unrecognized`
  before anything launches, and left untouched. Replacing it with defaults would lose its settings.
- **`--port`** (default 4747) is bound for `vigil monitor`. Use another port beside a running viewer.

Everything the run produced lands in `--work`:

| File | What it holds |
|---|---|
| `capture.vigil` | the whole session's capture, closed by `quit` |
| `monitor.ndjson` | `vigil monitor --json`, one event per line |
| `editor.log` | the Editor's output |
| `query.json`, `query-repro.json` | `vigil query --json` over the capture and over the repro's frames |
| `check.json`, `query-frame-N.json` | the verdict over the repro's frames and the worst frame's breakdown |

## 4. Read the result

The summary on stdout is the result, on failure too:

- `repro_frames`: the frame numbers the repro spanned, as the monitor saw them, or null when unknown.
- `repro_query`: the scopes over those frames.
- `check`: `vigil check`'s verdict over `repro_frames`. When those are unknown, the verdict covers
  the whole capture. A gap anywhere in the capture fails it.
- `monitor_gap_frames`: the frames the monitor flagged a gap in.
- `findings`: one entry per frame budget, with the worst frame, its cost and the scopes in it.

A finding states the scope, the frame, the measured cost against the budget, and what else that frame
spent time on.

To query further, run `vigil query <work>/capture.vigil --frames=N --top=20 --json`, or use `--scope`
or `--thread`. The capture stays after the run, and since `Vigil.cfg` no longer names it, no later
launch overwrites it.

## 5. Failure modes

| `failure` | Exit | Signal | Next step |
|---|---|---|---|
| `no_engine` | 2 | nothing answered on the console pipe within `--startup-timeout`, or the Editor exited first | read `editor.log`; on Linux without a display, check `xvfb-run` |
| `profiling_inactive` | 2 | the engine answered but refused `vigil.trace` as "not available to agents": no VigilAgent is running | use a profile that links VigilAgent (section 1); check `Enabled` in `Vigil.cfg` |
| `unknown_category` | 1 | `Unknown trace category '<name>'. Known categories: ...` | pick a name from that list |
| `refused` | 1 | the engine refused a repro line: closed to agents, or unparsable | use one of the commands in section 2 |
| `repro_failed` | 2 | `--repro-error` appeared; the message carries its text | the repro failed in the engine; read `editor.log` |
| `repro_unfinished` | 2 | `--repro-signal` never appeared | read `editor.log` |
| `port_in_use` | 2 | `vigil monitor` could not listen on `--port` | pass another `--port` |
| `config_unwritten` | 2 | no `Vigil.cfg` with a parcel header, and the Editor did not write its defaults | the Editor lacks VigilAgent, or crashed at start-up |
| `capture_unreadable` | 2 | `vigil query` could not load the capture, or the Editor had to be killed | the capture was cut off, so rerun |
| `empty_capture` | 2 | the capture holds no frames | the engine wrote elsewhere or quit at once |
| `check_unanswered` | 1 or 2 | `vigil check` printed no verdict: asked wrongly (a malformed budget), or the capture unreadable | fix the `--budget`/`--frame-budget` spelling, or rerun |
| `gaps` | 3 | `vigil check`, or the monitor with no assertion given, found gaps: a ring overflowed, so the capture cannot vouch for itself | fewer categories, a shorter repro, or a release build |
| `pulses_dropped` | 3 | `--max-dropped-pulses` failed: the fixed-step loop fell behind | that is the finding; read the pulse threads |
| `budget_missed` | 3 | a budget failed; `findings` names the frame | that is the finding |
| `launch_failed` | 4 | the Editor or `vigil` does not exist or would not start | build it, or fix the path |
| `work_locked` | 4 | a file in `--work` could not be replaced, usually the capture a previous run's Editor still holds | stop that Editor, or use another `--work` |
| `config_unrecognized` | 4 | `Vigil.cfg` is a parcel of other fields: the engine's `VigilConfiguration` changed | update `vigil_loop.py`; the file is left as it was |
| `config_inaccessible` | 4 | `Vigil.cfg` could not be read or written | check the build directory's permissions |
| `interrupted` | 130 | Ctrl+C or SIGTERM | the Editor and monitor were stopped and `Vigil.cfg` restored |

When a check fails on more than one count, the summary names the one that voids the most: gaps, then
dropped pulses, then budgets.

`console_pipe.py send --pipe PATH -- <command>` runs one console command in a running engine and
prints its answer, outside the loop. Its exit statuses are numbered as vigil's are: 0 OK, 1 misuse,
2 when no engine answers, and 3 for an `ERR` answer.

## Worked example: taking a screenshot

This was run on Windows in an `editor-profiling-windows` debug build, with the PowerShell command in
section 3. The loop exited 3 with `failure` set to `budget_missed`, and its summary read:

- `repro_frames`: `[129, 357]`, out of a 364-frame capture.
- `check`: run with `--frames=129:357`. It covered 229 frames, with `gap_count` 0 and
  `dropped_pulses` 0. Its frame budget read `measured_ms` 138.3 against 50 in `frame` 232.
- `findings[0]`: in frame 232, `PNG::Encode` took 138.3 ms inclusive, 52.0 ms of it self.
  `PNG::Compress` took 86.3 ms, all on `thread 4` beside `Aurora::RenderFrame`.
- `monitor_gap_frames`: `[]`, and `config_restored`: `true`.

The finding: one screenshot spends about 138 ms encoding on the render thread, three fifths of it in
compression. The monitor's frames 226 to 238 all span 16.3 to 17.4 ms, so the frame never waits on
it. The cost to cut is the render thread's.
