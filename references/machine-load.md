# Machine load

The host is shared with the user and with agents in sibling worktrees, so load one session
creates slows every other session and is blamed on whoever runs next. Ask before each instance of
load generation; permission for one flake does not carry to the next command or session.
`hooks/bash-guard.py` denies the common idioms, but it cannot see them all.

## Self-limiting load

Where the user has permitted a load test, give each generator its own deadline, so that no
cleanup step is needed for it to die:

```bash
# Arm the trap first, so an interrupt during startup still finds it.
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM
for _ in $(seq 1 4); do timeout -k 5 30 sh -c 'while :; do :; done' & done
wait
```

- Rely on the `timeout` — the `trap` never runs if the shell is killed, timed out, or moved to the
  background, and a trailing `kill $PIDS` runs only if the command reaches its end.
- Aim the trap at `jobs -p`, not `kill 0` — `kill 0` signals the whole process group and takes an
  interactive shell down with it.
- Use the smallest load and shortest deadline that reproduce the effect, and tell the user what
  you are about to start before you start it.

## A starved host

Before blaming your diff for a lint timeout, a slow build or a wall-clock trial failure, check
whether the machine is starved:

```bash
uptime                                                        # load average vs. core count
ps -eo pid,ppid,etime,time,pcpu,comm --sort=-pcpu | head -20  # who is burning CPU, and for how long
```

On Windows, `Get-CimInstance Win32_Processor | Select-Object LoadPercentage` and
`Get-Process | Sort-Object CPU -Descending | Select-Object -First 20` give the same picture.

- A load average well above the core count makes your timings meaningless; re-run when it drops.
- A `timeout after Ns` with no diagnostics is starvation, not a finding — real lint findings come
  with text.
- A long-running process reparented to PID 1 or `systemd --user` is an orphan from an abandoned
  session, not something the current work started.
- Report orphaned load generators to the user with their PIDs and ages, and ask before killing
  any — they may belong to a session that is still running.
