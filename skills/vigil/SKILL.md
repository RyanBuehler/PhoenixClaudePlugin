---
name: vigil
description: Profile a Phoenix Editor interaction with Vigil, from launch to a parsed finding, with no window touched.
---

Profile one interaction in the Editor end to end: configure profiling, launch the Editor, enable a
trace scope category, drive a repro through the console pipe, capture, stop, query and assert.
`vigil_loop.py run` is the whole loop. It needs no window and no manual step, and it prints one JSON
summary whose `failure` names what went wrong.

The human version of this loop, step by step, is `Docs/Vigil_DD.md` section 6.4 in the repository.

## Arguments

- **`<interaction>`**: what to profile, as console lines the Editor runs (the repro).
- **`<category>`**: the trace scope category that covers it (default: the owning module's).
- **`<budget>`** *(optional)*: `SCOPE=MS` per frame, which the loop asserts.

## 1. Build the two binaries

Build through `/phoe:build`, which owns the procedure. The loop needs these two binaries:

| Binary | Linux profile | Windows profile |
|---|---|---|
| Editor with VigilAgent in it | `editor-profiling` | `editor-profiling-windows` |
| `vigil`, without the viewer | `vigil-cli` | `vigil-cli-windows` |

A plain `editor` profile has no VigilAgent, so the loop fails there as `profiling_inactive`. Take each
binary's path from the build's `--json` result (`output_path`), not from a guess. Under
`Applications/Forge/.forge/<profile>/bin/` they are `editor`/`editor.exe` and `vigil`/`vigil.exe`.

## 2. Pick the category and the repro

- **The category**: the module's own name, from its `*Profile.h` (`Aurora`, `Prism`, `Mosaic`,
  `Soulforge`, ...). An unknown name fails as `unknown_category`, and the engine's answer lists every
  registered category, so a wrong guess costs one run.
- **The repro**: console lines open to agents. `help` over the pipe lists them. Python is not on the
  console pipe; a repro that needs a binding goes through Dispatch, which a profiling build does not
  carry. A repro that finishes asynchronously should name a file that appears when it is done
  (`--repro-signal`), as `aurora.screenshot` writes `.last-capture`.
- **The assertion**: `--frame-budget=SCOPE=MS` fails on the worst frame and names it. `--budget`
  averages across frames. With neither, the loop reports and asserts nothing.

## 3. Run the loop

Linux (bash):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vigil_loop.py run \
  --editor "$EDITOR_BIN" --vigil "$VIGIL_BIN" --work /tmp/vigil-run \
  --category Aurora \
  --repro "aurora.screenshot output_directory=/tmp/vigil-run/shots" \
  --repro-signal /tmp/vigil-run/shots/.last-capture \
  --frame-budget PNG::Encode=50
```

Windows (PowerShell): the same flags. Use `python`, not `python3`, and Windows paths. The console
pipe defaults to a per-run named pipe (`\\.\pipe\phoenix-vigil-<pid>`), because a Windows console
pipe must be a named pipe.

```powershell
python $env:CLAUDE_PLUGIN_ROOT\scripts\vigil_loop.py run `
  --editor $EditorExe --vigil $VigilExe --work C:\tmp\vigil-run `
  --category Aurora `
  --repro "aurora.screenshot output_directory=C:/tmp/vigil-run/shots" `
  --repro-signal C:\tmp\vigil-run\shots\.last-capture `
  --frame-budget PNG::Encode=50
```

The loop puts the build's `lib/` (beside `bin/`) on the Editor's library path. Windows needs this
for the Editor's DLLs. On Linux with no display, the loop starts the Editor under `xvfb-run -a` itself. `--launch-prefix ""`
turns that off, and another prefix replaces it.

The run has side effects:
- It rewrites `Configuration/Vigil.cfg` beside the Editor, turning profiling on and naming a capture
  file in `--work`. That Editor keeps profiling on later launches until the file is reset.
- It binds `--port` (default 4747) for `vigil monitor`. Use another port beside a running viewer.

Everything the run produced lands in `--work`:

| File | What it holds |
|---|---|
| `capture.vigil` | the whole session's capture, closed by `quit` |
| `monitor.ndjson` | `vigil monitor --json`, one event per line |
| `editor.log` | the Editor's output |
| `query.json`, `query-repro.json` | `vigil query --json` over the capture and over the repro's frames |
| `check.json`, `query-frame-N.json` | the verdict and the worst frame's breakdown |

## 4. Read the result

The summary on stdout is the result:

- `repro_frames`: the frame numbers the repro spanned, as the monitor saw them.
- `repro_query`: the scopes over those frames.
- `check`: `vigil check`'s verdict.
- `findings`: one entry per frame budget, with the worst frame, its cost and the scopes in it.

A finding states the scope, the frame, the measured cost against the budget, and what else that frame
spent time on.

To query further, run `vigil query <work>/capture.vigil --frames=N --top=20 --json` (or `--scope`,
`--thread`). The capture stays after the run.

## 5. Failure modes

| `failure` | Exit | Signal | Next step |
|---|---|---|---|
| `no_engine` | 2 | nothing answered on the console pipe within `--startup-timeout`, or the Editor exited first | read `editor.log`; on Linux without a display, check `xvfb-run` |
| `profiling_inactive` | 2 | the engine answered but refused `vigil.trace` as "not available to agents", so it has no VigilAgent | build the `editor-profiling` profile; check `Enabled` in `Vigil.cfg` |
| `unknown_category` | 1 | `Unknown trace category '<name>'. Known categories: ...` | pick a name from that list |
| `refused` | 1 | the engine refused a repro line (not open to agents, unparsable) | use `help` for what agents may run |
| `repro_unfinished` | 2 | `--repro-signal` never appeared | the repro failed in the engine; read `editor.log` |
| `port_in_use` | 2 | `vigil monitor` could not listen on `--port` | pass another `--port` |
| `config_unwritten` | 2 | no readable `Vigil.cfg`, and the Editor did not write its defaults | the Editor lacks VigilAgent, or crashed at start-up |
| `capture_unreadable` | 2 | `vigil query` could not load the capture, or the Editor had to be killed | the capture was cut off, so rerun |
| `empty_capture` | 2 | the capture holds no frames | the engine wrote elsewhere or quit at once; check `Vigil.cfg`'s `CaptureFile` |
| `gaps` | 3 | `vigil check` found gaps: the ring overflowed and the capture cannot vouch for itself | fewer categories, a shorter repro, or a release build |
| `budget_missed` | 3 | a budget failed; `findings` names the frame | that is the finding |

`console_pipe.py send --pipe PATH -- <command>` runs one console command in a running engine and
prints its answer, outside the loop. It exits 0 for OK, 1 for ERR, 2 for misuse and 3 when no engine
answers.

## Worked example: taking a screenshot

This is the Windows command in section 3, run against an `editor-profiling-windows` debug build. It
exited 3, `budget_missed`. The summary, trimmed:

```json
"enabled": "Aurora",
"attached": true,
"repro_frames": [129, 362],
"editor_exit": 0,
"query": {"frame_count": 369, "average_frame_ms": 16.83, "peak_frame_ms": 22.45},
"check": {"passed": false, "gap_count": 0, "dropped_pulses": 0,
  "frame_budgets": [{"scope": "PNG::Encode", "budget_ms": 50.0, "measured_ms": 130.2868, "frame": 233}]},
"findings": [{"scope": "PNG::Encode", "worst_frame": 233, "measured_ms": 130.2868, "frame_ms": 16.5361,
  "frame_scopes": [
    {"name": "PNG::Encode",   "thread": "thread 4", "inclusive_ms": 130.2868, "self_ms": 50.0653},
    {"name": "PNG::Compress", "thread": "thread 4", "inclusive_ms": 80.2215,  "self_ms": 80.2215}, ...]}],
"failure": "budget_missed"
```

The finding, read from that summary:
- One screenshot spends 130 ms encoding PNG. 80 ms of it is `PNG::Compress`, the other 50 ms is the
  encoder's own work.
- It all runs on `thread 4`, the thread that runs `Aurora::RenderFrame`.
- Frame 233 itself measured 16.5 ms. The frames around it in `monitor.ndjson` span 16.5 to 17.1 ms.
  So the encode stalls the render thread, not the loop.
- Cut `PNG::Compress` first.

Threads named only `thread N` registered before the capture file opened. Their names are sent once
per process, and those sends happened before the file opened (Vigil_DD section 1.2).

Each failure case, run live against the same build:

```
$ console_pipe.py send --pipe '\\.\pipe\phoenix-nobody-here' --wait 1 -- vigil.trace Aurora on
console_pipe: no engine is listening on the console pipe \\.\pipe\phoenix-nobody-here (No such file or directory)   [exit 3]

$ vigil_loop.py run ... --startup-timeout 1
{"failure": "no_engine", "message": "no engine attached within 1 s: no engine is listening on the console pipe ..."}   [exit 2]

$ vigil_loop.py run ... --category Auroa
{"failure": "unknown_category", "message": "ERR Unknown trace category 'Auroa'. Known categories: Arbiter, Aurora,
 Compression, Engine, Impulse, Ledger, Montage, Mosaic, Networking, Prism, Realm, Sonic, Soulforge, Vulkan,
 WindowsInput, WindowsLiaison, WindowsPane"}   [exit 1]

$ console_pipe.py send --pipe ... -- vigil.trace Aurora on      # the same Editor with Enabled 0 in Vigil.cfg
ERR Command 'vigil.trace' is not available to agents   [exit 1; the loop reports profiling_inactive]
```
