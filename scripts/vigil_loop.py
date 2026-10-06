#!/usr/bin/env python3
"""Profile one repro in a Phoenix Editor with Vigil, from launch to a parsed finding, with no window touched.

`run` drives the whole loop and prints one JSON summary on stdout:

  1. configure  write Vigil.cfg beside the Editor: profiling on, streaming to --port, and a capture file
  2. watch      start `vigil monitor --json` on --port, so the engine has a reader to attach to
  3. launch     start the Editor with --console-pipe, so commands reach it and answers come back
  4. attach     `vigil.trace <category> on` over the pipe -- the first answer proves an engine is there
  5. repro      send each --repro line over the pipe, then wait for --repro-signal and --settle
  6. stop       `vigil.trace <category> off`, then `quit`, which closes the capture whole
  7. query      `vigil query --json` over the whole capture and over the repro's frames
  8. assert     `vigil check --json` with the budgets given, and the worst frame of each frame budget

`configure` does step 1 alone, for an engineer who launches the Editor by hand.

Vigil.cfg is a text parcel the engine writes and checksums by its struct's size, so it is never
written from scratch here: an existing one is read and its fields rewritten. A missing or unreadable
one is first replaced by the engine's own defaults, by launching the Editor once with --quit.

Exit status follows the vigil verbs: 0 the loop ran and every assertion held, 1 misuse (bad arguments,
an unknown category, a repro the engine refused), 2 no answer (no engine attached, profiling off, an
empty or unreadable capture), 3 an assertion failed (a budget missed, gaps present). The summary's
`failure` names which.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PASSED = 0
MISUSED = 1
UNANSWERED = 2
FAILED = 3

PARCEL_MAGIC = 1346915928  # "PHNX", 0x50484E58
# Header (magic, type id, version), checksum, then the struct's own version: five tokens before the fields.
PREFIX_TOKENS = 5
CONFIG_NAME = "Vigil.cfg"
DEFAULT_PORT = 4747
NOT_OPEN_TO_AGENTS = "is not available to agents"
UNKNOWN_CATEGORY = "Unknown trace category"

_SPEC = importlib.util.spec_from_file_location("console_pipe", Path(__file__).resolve().with_name("console_pipe.py"))
console_pipe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(console_pipe)


class LoopFailure(Exception):
	"""A step that ends the loop: its exit status, the summary's failure name and a sentence for the reader."""

	def __init__(self, status, failure, message):
		super().__init__(message)
		self.status = status
		self.failure = failure


# --- Vigil.cfg -------------------------------------------------------------------------------------

class TokenReader:
	def __init__(self, tokens):
		self.tokens = tokens
		self.position = 0

	def Take(self):
		if self.position >= len(self.tokens):
			raise ValueError("the file ends before its last field")
		token = self.tokens[self.position]
		self.position += 1
		if not token.isdigit():
			raise ValueError(f"'{token}' is not a number")
		return int(token)

	def TakeBool(self):
		value = self.Take()
		if value not in (0, 1):
			raise ValueError(f"{value} is not a boolean")
		return value == 1

	def TakeString(self):
		count = self.Take()
		if count > len(self.tokens) - self.position:
			raise ValueError("a string runs past the end of the file")
		values = [self.Take() for _ in range(count)]
		if any(value > 255 for value in values):
			raise ValueError("a string holds a value that is not a byte")
		return bytes(values).decode("utf-8")

	def TakeStrings(self):
		count = self.Take()
		if count > len(self.tokens) - self.position:
			raise ValueError("a list runs past the end of the file")
		return [self.TakeString() for _ in range(count)]


def EncodeString(text):
	data = text.encode("utf-8")
	return [str(len(data)), *(str(value) for value in data)]


def ParseConfig(text):
	"""Split a Vigil.cfg into the prefix the engine owns and VigilConfiguration's fields, in declaration order."""
	tokens = text.split()
	if len(tokens) < PREFIX_TOKENS or tokens[0] != str(PARCEL_MAGIC):
		raise ValueError("it does not open with a parcel header")
	reader = TokenReader(tokens)
	reader.position = PREFIX_TOKENS
	fields = {
		"Enabled": reader.TakeBool(),
		"Host": reader.TakeString(),
		"Port": reader.Take(),
		"CaptureFile": reader.TakeString(),
		"EnabledTraceCategories": reader.TakeStrings(),
	}
	if reader.position != len(tokens):
		raise ValueError("it holds more than the fields this script knows; VigilConfiguration has changed")
	return tokens[:PREFIX_TOKENS], fields


def FormatConfig(prefix, fields):
	tokens = list(prefix)
	tokens.append("1" if fields["Enabled"] else "0")
	tokens += EncodeString(fields["Host"])
	tokens.append(str(fields["Port"]))
	tokens += EncodeString(fields["CaptureFile"])
	tokens.append(str(len(fields["EnabledTraceCategories"])))
	for category in fields["EnabledTraceCategories"]:
		tokens += EncodeString(category)
	return " ".join(tokens)


def EditorEnvironment(editor_command):
	"""Forge puts an Editor's shared libraries in lib/ beside bin/, which Windows finds only through PATH."""
	environment = dict(os.environ)
	if not editor_command:
		return environment
	library = Path(editor_command[-1]).resolve().parent.parent / "lib"
	if library.is_dir():
		variable = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
		environment[variable] = os.pathsep.join(filter(None, [str(library), environment.get(variable)]))
	return environment


def SeedConfig(config_path, editor_command, timeout):
	"""Have the engine write its defaults: it replaces a Vigil.cfg it cannot parse, and --quit ends it at once."""
	config_path.parent.mkdir(parents=True, exist_ok=True)
	config_path.write_text("unparsable\n")
	try:
		subprocess.run([*editor_command, "--quit"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL, timeout=timeout, check=False, cwd=config_path.parent,
			env=EditorEnvironment(editor_command))
	except subprocess.TimeoutExpired as error:
		raise LoopFailure(UNANSWERED, "config_unwritten",
			f"the Editor launched to write {config_path} did not exit within {timeout:g} s") from error


def Configure(config_path, editor_command, port, capture_file, categories, timeout):
	"""Write Vigil.cfg with profiling on, return the fields written."""
	try:
		prefix, fields = ParseConfig(config_path.read_text())
	except (OSError, ValueError, UnicodeDecodeError):
		if not editor_command:
			raise LoopFailure(UNANSWERED, "config_unwritten",
				f"{config_path} is missing or unreadable, and no Editor was given to write its defaults")
		SeedConfig(config_path, editor_command, timeout)
		try:
			prefix, fields = ParseConfig(config_path.read_text())
		except (OSError, ValueError, UnicodeDecodeError) as error:
			raise LoopFailure(UNANSWERED, "config_unwritten",
				f"the Editor did not leave a readable {config_path}: {error}. Is VigilAgent in this build?") from error
	fields.update({
		"Enabled": True,
		"Host": "127.0.0.1",
		"Port": port,
		"CaptureFile": capture_file,
		"EnabledTraceCategories": categories or ["None"],
	})
	config_path.write_text(FormatConfig(prefix, fields))
	return fields


# --- the loop --------------------------------------------------------------------------------------

def DefaultPipePath():
	if os.name == "nt":
		return f"\\\\.\\pipe\\phoenix-vigil-{os.getpid()}"
	# Short and in /tmp: the reply socket's path must fit sun_path's 108 bytes.
	return f"/tmp/phoenix-vigil-{os.getpid()}.fifo"


def DefaultLaunchPrefix():
	if os.name == "nt" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
		return []
	return ["xvfb-run", "-a"] if shutil.which("xvfb-run") else []


def ReadEvents(path):
	events = []
	try:
		lines = Path(path).read_text(errors="replace").splitlines()
	except OSError:
		return events
	for line in lines:
		try:
			events.append(json.loads(line))
		except json.JSONDecodeError:
			continue
	return events


def NewestFrame(path):
	frames = [event["frame"] for event in ReadEvents(path) if event.get("event") == "frame"]
	return frames[-1] if frames else None


def WaitForEvent(path, name, process, seconds):
	deadline = time.monotonic() + seconds
	while time.monotonic() < deadline:
		if any(event.get("event") == name for event in ReadEvents(path)):
			return True
		if process.poll() is not None:
			return False
		time.sleep(0.1)
	return False


def SendOrFail(pipe, command, editor, step):
	"""Run one command over the pipe; an engine that is gone, or that refuses, ends the loop with the reason."""
	try:
		answer = console_pipe.Send(pipe, command, 0.0, console_pipe.DEFAULT_REPLY_SECONDS)
	except console_pipe.NoAnswer as error:
		code = editor.poll()
		detail = f"; the Editor exited with {code}" if code is not None else ""
		raise LoopFailure(UNANSWERED, "no_engine", f"{step}: {error}{detail}") from error
	if console_pipe.ClassifyAnswer(answer) != console_pipe.ANSWERED:
		raise LoopFailure(MISUSED, "refused", f"{step}: the engine refused '{command}': {answer}")
	return answer


def Attach(pipe, category, editor, seconds):
	"""The first command doubles as the attach probe: it waits out the Editor's start-up."""
	deadline = time.monotonic() + seconds
	while True:
		try:
			answer = console_pipe.Send(pipe, f"vigil.trace {category} on", 0.5, console_pipe.DEFAULT_REPLY_SECONDS)
			break
		except console_pipe.NoAnswer as error:
			code = editor.poll()
			if code is not None:
				raise LoopFailure(UNANSWERED, "no_engine",
					f"the Editor exited with {code} before its console pipe answered; read editor.log") from error
			if time.monotonic() >= deadline:
				raise LoopFailure(UNANSWERED, "no_engine",
					f"no engine attached within {seconds:g} s: {error}") from error
	if console_pipe.ClassifyAnswer(answer) == console_pipe.ANSWERED:
		return answer
	if NOT_OPEN_TO_AGENTS in answer:
		raise LoopFailure(UNANSWERED, "profiling_inactive",
			f"the engine answered but has no vigil.trace, so VigilAgent is not running ({answer}); build an "
			"editor-profiling profile and check Vigil.cfg's Enabled")
	if UNKNOWN_CATEGORY in answer:
		raise LoopFailure(MISUSED, "unknown_category", answer)
	raise LoopFailure(MISUSED, "refused", answer)


def RunVerb(vigil, arguments, output_path):
	result = subprocess.run([vigil, *arguments], capture_output=True, text=True, check=False)
	Path(output_path).write_text(result.stdout)
	answer = None
	if result.stdout.strip():
		try:
			answer = json.loads(result.stdout)
		except json.JSONDecodeError:
			answer = None
	return result.returncode, answer, result.stderr.strip()


def Stop(process, seconds):
	if process.poll() is not None:
		return process.returncode
	try:
		return process.wait(seconds)
	except subprocess.TimeoutExpired:
		process.kill()
		process.wait()
		return None


def Run(args):
	work = Path(args.work).resolve()
	work.mkdir(parents=True, exist_ok=True)
	capture = work / "capture.vigil"
	monitor_path = work / "monitor.ndjson"
	pipe = args.pipe or DefaultPipePath()
	launch = [*(args.launch_prefix.split() if args.launch_prefix is not None else DefaultLaunchPrefix()), args.editor]
	summary = {"work": str(work), "capture": str(capture), "pipe": pipe, "port": args.port, "categories": args.category}
	for stale in (capture, monitor_path):
		stale.unlink(missing_ok=True)

	config_path = Path(args.editor).resolve().parent / "Configuration" / CONFIG_NAME
	Configure(config_path, launch, args.port, capture.as_posix(), [], args.startup_timeout)
	summary["config"] = str(config_path)

	monitor = subprocess.Popen(
		[args.vigil, "monitor", "--json", f"--port={args.port}", f"--seconds={args.monitor_seconds:g}"],
		stdin=subprocess.DEVNULL, stdout=monitor_path.open("w"), stderr=(work / "monitor.err").open("w"))
	editor = None
	try:
		if not WaitForEvent(monitor_path, "listening", monitor, 10):
			raise LoopFailure(UNANSWERED, "port_in_use",
				f"vigil monitor did not listen on port {args.port}: {(work / 'monitor.err').read_text().strip()}")

		editor = subprocess.Popen([*launch, f"--console-pipe={pipe}"], cwd=work, stdin=subprocess.DEVNULL,
			stdout=(work / "editor.log").open("w"), stderr=subprocess.STDOUT, env=EditorEnvironment(launch))

		for index, category in enumerate(args.category):
			# Only the first waits out start-up; every answer is read for the same refusals.
			answer = Attach(pipe, category, editor, args.startup_timeout if index == 0 else 0.0)
			summary["enabled"] = answer.removeprefix("OK ")
		summary["attached"] = WaitForEvent(monitor_path, "connected", monitor, 10)

		# The capture's frames before the repro are start-up; the repro's are those the monitor reports after this.
		time.sleep(args.settle)
		before = NewestFrame(monitor_path)
		for line in args.repro:
			SendOrFail(pipe, line, editor, "repro")
		if args.repro_signal:
			deadline = time.monotonic() + args.repro_timeout
			while not Path(args.repro_signal).exists():
				if time.monotonic() >= deadline:
					raise LoopFailure(UNANSWERED, "repro_unfinished",
						f"{args.repro_signal} did not appear within {args.repro_timeout:g} s of the repro")
				time.sleep(0.1)
		time.sleep(args.settle)
		after = NewestFrame(monitor_path)
		summary["repro_frames"] = [before + 1 if before is not None else None, after]

		for category in args.category:
			SendOrFail(pipe, f"vigil.trace {category} off", editor, "stop")
		SendOrFail(pipe, "quit", editor, "stop")
		summary["editor_exit"] = Stop(editor, args.exit_timeout)
		if summary["editor_exit"] is None:
			raise LoopFailure(UNANSWERED, "capture_unreadable",
				f"the Editor did not exit within {args.exit_timeout:g} s of quit and was killed; its capture is cut off")
		WaitForEvent(monitor_path, "disconnected", monitor, 5)
	finally:
		if editor is not None and editor.poll() is None:
			editor.kill()
		monitor.terminate()
		Stop(monitor, 10)

	code, whole, error = RunVerb(args.vigil, ["query", str(capture), "--json", "--top=10"], work / "query.json")
	if code != 0 or whole is None:
		raise LoopFailure(UNANSWERED, "capture_unreadable", f"vigil query exited {code}: {error}")
	summary["query"] = {key: whole[key] for key in ("frame_count", "first_frame", "last_frame", "average_frame_ms",
		"peak_frame_ms", "hottest_scope", "hottest_self_ms")}
	if not whole["frame_count"]:
		raise LoopFailure(UNANSWERED, "empty_capture",
			"the capture holds no frames: the engine recorded nothing before it quit, or wrote to another file")

	first, last = summary["repro_frames"]
	if first is not None and last is not None and first <= last:
		code, window, error = RunVerb(args.vigil, ["query", str(capture), "--json", "--top=10", f"--frames={first}:{last}"],
			work / "query-repro.json")
		if code == 0 and window is not None:
			summary["repro_query"] = {"frame_count": window["frame_count"], "scopes": window["scopes"]}

	assertions = [f"--budget={value}" for value in args.budget] + [f"--frame-budget={value}" for value in args.frame_budget]
	if args.max_dropped_pulses is not None:
		assertions.append(f"--max-dropped-pulses={args.max_dropped_pulses}")
	if not assertions:
		return PASSED, summary

	code, verdict, error = RunVerb(args.vigil, ["check", str(capture), "--json", *assertions], work / "check.json")
	if verdict is None:
		raise LoopFailure(code or UNANSWERED, "check_unanswered", f"vigil check exited {code}: {error}")
	summary["check"] = verdict
	findings = []
	for budget in verdict.get("frame_budgets", []):
		frame = budget.get("frame")
		finding = {"scope": budget["scope"], "worst_frame": frame, "measured_ms": budget["measured_ms"],
			"budget_ms": budget["budget_ms"], "passed": budget["passed"]}
		if frame is not None:
			_, breakdown, _ = RunVerb(args.vigil, ["query", str(capture), "--json", "--top=8", f"--frames={frame}"],
				work / f"query-frame-{frame}.json")
			if breakdown is not None:
				finding["frame_ms"] = breakdown["average_frame_ms"]
				finding["frame_scopes"] = [{key: scope[key] for key in ("name", "thread", "inclusive_ms", "self_ms", "calls")}
					for scope in breakdown["scopes"]]
		findings.append(finding)
	summary["findings"] = findings
	if code == 0:
		return PASSED, summary
	if code == 3:
		summary["failure"] = "gaps" if not verdict.get("gaps_passed", True) else "budget_missed"
		return FAILED, summary
	raise LoopFailure(code, "check_unanswered", f"vigil check exited {code}: {error}")


def Main(argv):
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	sub = parser.add_subparsers(dest="action", required=True)

	configure = sub.add_parser("configure", help="write Vigil.cfg beside an Editor with profiling on")
	configure.add_argument("--editor", required=True, help="the Editor executable from a profiling build")
	configure.add_argument("--port", type=int, default=DEFAULT_PORT)
	configure.add_argument("--capture", default="", help="the .vigil file to write for the whole session")
	configure.add_argument("--category", action="append", default=[], help="a trace scope category on from launch")
	configure.add_argument("--timeout", type=float, default=180.0, help="seconds the defaults-writing launch may take")

	run = sub.add_parser("run", help="run the whole loop and print a JSON summary")
	run.add_argument("--editor", required=True, help="the Editor executable from a profiling build")
	run.add_argument("--vigil", required=True, help="the vigil executable")
	run.add_argument("--work", required=True, help="directory for the capture, the logs and every answer")
	run.add_argument("--category", action="append", required=True,
		help="trace scope category to enable for the repro; repeat for several")
	run.add_argument("--repro", action="append", default=[], help="console line to run as the repro, in order")
	run.add_argument("--repro-signal", help="a file whose appearance says the repro finished")
	run.add_argument("--repro-timeout", type=float, default=60.0)
	run.add_argument("--settle", type=float, default=2.0, help="seconds of frames before and after the repro")
	run.add_argument("--budget", action="append", default=[], help="SCOPE=MS, passed to vigil check")
	run.add_argument("--frame-budget", action="append", default=[], help="SCOPE=MS, passed to vigil check")
	run.add_argument("--max-dropped-pulses", type=int)
	run.add_argument("--port", type=int, default=DEFAULT_PORT)
	run.add_argument("--pipe", help="console pipe path (default: a per-run name)")
	run.add_argument("--launch-prefix", help="words before the Editor, such as 'xvfb-run -a' (default: xvfb-run when there is no display)")
	run.add_argument("--startup-timeout", type=float, default=180.0)
	run.add_argument("--exit-timeout", type=float, default=60.0)
	run.add_argument("--monitor-seconds", type=float, default=900.0)
	args = parser.parse_args(argv)

	if args.action == "configure":
		try:
			fields = Configure(Path(args.editor).resolve().parent / "Configuration" / CONFIG_NAME, [args.editor],
				args.port, args.capture, args.category, args.timeout)
		except LoopFailure as failure:
			print(f"vigil_loop: {failure}", file=sys.stderr)
			return failure.status
		print(json.dumps(fields))
		return PASSED

	try:
		status, summary = Run(args)
	except LoopFailure as failure:
		print(json.dumps({"failure": failure.failure, "message": str(failure)}, indent="\t"))
		print(f"vigil_loop: {failure}", file=sys.stderr)
		return failure.status
	print(json.dumps(summary, indent="\t"))
	return status


if __name__ == "__main__":
	sys.exit(Main(sys.argv[1:]))
