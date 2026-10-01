#!/usr/bin/env python3
"""Run a long command detached and block on it inside one tool call.

A Forge build, verify or bootstrap can outlive the ten-minute Bash timeout. Polling its log costs
one full-context request per peek, so this script does the waiting instead: `start` launches the
command in its own session, and `start` and `wait` both block for up to --timeout seconds and then
report once. A run that outlives the timeout is reported as still running, and another `wait`
resumes it.

Completion is read from an exit-code file the wrapper writes when the command exits, never from the
log's wording, so a change in Forge's output cannot make a finished run look unfinished or the
reverse.

  forge_wait.py start --log <path> -- <command...>
  forge_wait.py wait  --log <path>

Exit status: the command's own on completion, STILL_RUNNING if the timeout passed first, DIED if
the command vanished without recording one.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Under the harness's ten-minute Bash cap, with room to print the report.
DEFAULT_TIMEOUT_SECONDS = 570
POLL_SECONDS = 2

STILL_RUNNING = 124
DIED = 125

# A log this short prints whole. A longer one prints its head and tail, plus every FAILED line
# from the elided middle: a Forge verdict can print above the findings it summarizes.
MAX_WHOLE_LINES = 250
HEAD_LINES = 120
TAIL_LINES = 80
FAILURE_MARKER = "FAILED"

# The exit file is renamed into place so a reader never sees it half-written.
WRAPPER = '"$@" > "$FORGE_WAIT_LOG" 2>&1; echo $? > "$FORGE_WAIT_LOG.exit.tmp"; ' \
	'mv "$FORGE_WAIT_LOG.exit.tmp" "$FORGE_WAIT_LOG.exit"'


def GetExitPath(log):
	return Path(f"{log}.exit")


def GetPidPath(log):
	return Path(f"{log}.pid")


def IsAlive(pid):
	try:
		os.kill(pid, 0)
	except ProcessLookupError:
		return False
	except PermissionError:
		return True
	# A finished child of this process lingers as a zombie until reaped; reap it so it reads dead.
	try:
		reaped, _ = os.waitpid(pid, os.WNOHANG)
		return reaped == 0
	except ChildProcessError:
		return True


def ReadPid(log):
	try:
		return int(GetPidPath(log).read_text().strip())
	except (OSError, ValueError):
		return None


def FormatDuration(seconds):
	seconds = int(seconds)
	return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def GetElapsed(log):
	try:
		return time.time() - GetPidPath(log).stat().st_mtime
	except OSError:
		return 0.0


def ReadLines(log):
	try:
		return Path(log).read_text(errors="replace").splitlines()
	except OSError:
		return []


def PrintLog(log):
	lines = ReadLines(log)
	if len(lines) <= MAX_WHOLE_LINES:
		print("\n".join(lines))
		return
	middle = lines[HEAD_LINES:-TAIL_LINES]
	failures = [line for line in middle if FAILURE_MARKER in line]
	print("\n".join(lines[:HEAD_LINES]))
	print(f"... {len(middle)} lines elided; {len(failures)} {FAILURE_MARKER} line(s) from them follow"
		f" (full log: {log}) ...")
	if failures:
		print("\n".join(failures))
		print("...")
	print("\n".join(lines[-TAIL_LINES:]))


def Report(log, script):
	"""Print the outcome and return the exit status to leave with, or None while still running."""
	exit_path = GetExitPath(log)
	if exit_path.exists():
		code = int(exit_path.read_text().strip() or DIED)
		print(f"forge_wait: exited {code} after {FormatDuration(GetElapsed(log))} -- {log}")
		PrintLog(log)
		return code
	pid = ReadPid(log)
	if pid is None or not IsAlive(pid):
		# The exit file may have landed between the two checks.
		if exit_path.exists():
			return Report(log, script)
		print(f"forge_wait: the command died without recording an exit status -- {log}")
		PrintLog(log)
		return DIED
	return None


def Wait(log, timeout, script):
	deadline = time.monotonic() + timeout
	while True:
		code = Report(log, script)
		if code is not None:
			return code
		if time.monotonic() >= deadline:
			break
		time.sleep(POLL_SECONDS)
	tail = [line for line in ReadLines(log) if line.strip()][-3:]
	print(f"forge_wait: still running after {FormatDuration(GetElapsed(log))} (pid {ReadPid(log)}).")
	print(f"Call again, in the foreground: python3 {script} wait --log {log}")
	if tail:
		print("\n".join(tail))
	return STILL_RUNNING


def Start(log, command, timeout, script):
	pid = ReadPid(log)
	if pid is not None and IsAlive(pid) and not GetExitPath(log).exists():
		print(f"forge_wait: {log} already belongs to running pid {pid}; wait on it or pick another log.")
		return 2
	Path(log).parent.mkdir(parents=True, exist_ok=True)
	for stale in (GetExitPath(log), Path(f"{log}.exit.tmp")):
		stale.unlink(missing_ok=True)
	child = subprocess.Popen(
		["sh", "-c", WRAPPER, "sh", *command],
		env={**os.environ, "FORGE_WAIT_LOG": log},
		stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
		start_new_session=True)
	GetPidPath(log).write_text(f"{child.pid}\n")
	print(f"forge_wait: started pid {child.pid}: {' '.join(command)}")
	return Wait(log, timeout, script)


def Main(argv):
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	sub = parser.add_subparsers(dest="action", required=True)
	for name in ("start", "wait"):
		action = sub.add_parser(name)
		action.add_argument("--log", required=True, help="where the command's output goes")
		action.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
			help="seconds to block before reporting the run as still going")
		if name == "start":
			action.add_argument("command", nargs=argparse.REMAINDER)
	args = parser.parse_args(argv)
	log = os.path.abspath(args.log)
	script = os.path.abspath(__file__)
	if args.action == "wait":
		return Wait(log, args.timeout, script)
	command = args.command[1:] if args.command[:1] == ["--"] else args.command
	if not command:
		parser.error("start needs a command after --")
	return Start(log, command, args.timeout, script)


if __name__ == "__main__":
	sys.exit(Main(sys.argv[1:]))
