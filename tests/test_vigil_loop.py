#!/usr/bin/env python3
"""Unit tests for scripts/vigil_loop.py.

Vigil.cfg is tested as text in the layout the engine writes. The attach step is tested against a
stand-in engine on the platform's console pipe channel, because how each refusal reads is the
contract the loop's failure names rest on.
"""

import contextlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vigil_loop.py"
SPEC = importlib.util.spec_from_file_location("vigil_loop", SCRIPT)
vigil_loop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vigil_loop)
console_pipe = vigil_loop.console_pipe

# Copied from the file a Windows editor-profiling Editor wrote: header, checksum, struct version, then
# Enabled 0, Host "127.0.0.1", Port 4747, CaptureFile "", EnabledTraceCategories {"None"}.
PREFIX = "1346915928 628732253453807578 0 168 0"
DEFAULTS = PREFIX + " 0 9 49 50 55 46 48 46 48 46 49 4747 0 1 4 78 111 110 101"


def Frame(payload):
	data = payload.encode("utf-8")
	return f"{len(data)}\n".encode("ascii") + data


class Running:
	"""An Editor process still running, as far as the attach step can tell."""

	def poll(self):
		return None


class Exited:
	def __init__(self, code):
		self.code = code

	def poll(self):
		return self.code


class StandInEngine:
	"""Answers one request on the console pipe channel with a fixed answer."""

	def __init__(self, answer):
		self.answer = answer
		self.received = None
		self._tmp = tempfile.TemporaryDirectory()
		if os.name == "nt":
			from multiprocessing.connection import Listener
			self.path = f"\\\\.\\pipe\\phoe-vigil-loop-test-{os.getpid()}-{id(self)}"
			self._listener = Listener(self.path, family="AF_PIPE")
		else:
			self.path = str(Path(self._tmp.name) / "console.fifo")
			self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			self._listener.bind(self.path + console_pipe.SOCKET_SUFFIX)
			self._listener.listen(1)
		self._thread = threading.Thread(target=self._Serve, daemon=True)
		self._thread.start()

	def _Serve(self):
		if os.name == "nt":
			with self._listener.accept() as client:
				self.received = client.recv_bytes()
				client.send_bytes(self.answer)
			return
		client, _ = self._listener.accept()
		with client:
			line = b""
			while not line.endswith(b"\n"):
				chunk = client.recv(64)
				if not chunk:
					break
				line += chunk
			self.received = line
			client.sendall(self.answer)

	def Close(self):
		self._thread.join(10)
		self._listener.close()
		self._tmp.cleanup()


def AbsentPipe():
	if os.name == "nt":
		return f"\\\\.\\pipe\\phoe-vigil-loop-absent-{os.getpid()}"
	return str(Path(tempfile.gettempdir()) / f"phoe-vigil-loop-absent-{os.getpid()}.fifo")


class ConfigTests(unittest.TestCase):

	def test_the_engine_defaults_read_as_vigil_configuration_fields(self):
		prefix, fields = vigil_loop.ParseConfig(DEFAULTS)
		self.assertEqual(" ".join(prefix), PREFIX)
		self.assertEqual(fields, {"Enabled": False, "Host": "127.0.0.1", "Port": 4747, "CaptureFile": "",
			"EnabledTraceCategories": ["None"]})

	def test_fields_written_back_read_the_same_and_keep_the_engine_prefix(self):
		prefix, fields = vigil_loop.ParseConfig(DEFAULTS)
		fields.update({"Enabled": True, "Port": 4848, "CaptureFile": "C:/work/capture.vigil",
			"EnabledTraceCategories": ["Aurora", "Prism"]})
		text = vigil_loop.FormatConfig(prefix, fields)
		self.assertTrue(text.startswith(PREFIX + " 1 "))
		self.assertEqual(vigil_loop.ParseConfig(text), (prefix, fields))

	def test_the_defaults_format_back_to_the_text_they_came_from(self):
		self.assertEqual(vigil_loop.FormatConfig(*vigil_loop.ParseConfig(DEFAULTS)), DEFAULTS)

	def test_a_file_that_is_not_this_struct_is_refused(self):
		for text in ("", "unparsable", "1 2 3 4 5 0 0 0 0 0",          # no parcel header
				DEFAULTS.rsplit(" ", 2)[0],                             # cut short
				DEFAULTS + " 7",                                        # a field this script does not know
				DEFAULTS.replace(" 0 9 49", " 2 9 49", 1),             # a boolean that is not 0 or 1
				DEFAULTS.replace("49 50 55", "49 500 55", 1)):          # a string byte past 255
			with self.assertRaises(ValueError, msg=text):
				vigil_loop.ParseConfig(text)

	def test_only_a_file_without_a_parcel_header_is_not_a_parcel(self):
		for text in ("", "unparsable", "1 2 3 4 5 0 0 0 0 0"):
			with self.assertRaises(vigil_loop.NotAParcel, msg=text):
				vigil_loop.ParseConfig(text)
		for text in (DEFAULTS + " 7", DEFAULTS.rsplit(" ", 2)[0]):
			try:
				vigil_loop.ParseConfig(text)
			except vigil_loop.NotAParcel:
				self.fail(f"a parcel with other fields is still a parcel: {text}")
			except ValueError:
				pass


def SeedingEditor(directory, marker=None):
	"""Stands in for an engine that replaces a Vigil.cfg it cannot parse, in its Configuration directory."""
	editor = Path(directory) / "editor.py"
	editor.write_text(textwrap.dedent(f"""
		import sys
		from pathlib import Path
		assert sys.argv[1:] == ["--quit"]
		assert Path("Vigil.cfg").read_text().strip() == "unparsable"
		Path("Vigil.cfg").write_text({DEFAULTS!r})
		if {str(marker) if marker else ""!r}:
			Path({str(marker) if marker else ""!r}).write_text("launched")
	"""))
	return [sys.executable, str(editor)]


class ConfigureTests(unittest.TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.config = Path(self._tmp.name) / "Configuration" / "Vigil.cfg"

	def tearDown(self):
		self._tmp.cleanup()

	def test_an_existing_file_has_profiling_turned_on_and_its_prefix_kept(self):
		self.config.parent.mkdir()
		self.config.write_text(DEFAULTS)
		fields = vigil_loop.Configure(self.config, None, 4848, "C:/work/capture.vigil", ["Aurora"], 5)
		self.assertTrue(fields["Enabled"])
		prefix, written = vigil_loop.ParseConfig(self.config.read_text())
		self.assertEqual(" ".join(prefix), PREFIX)
		self.assertEqual(written, {"Enabled": True, "Host": "127.0.0.1", "Port": 4848,
			"CaptureFile": "C:/work/capture.vigil", "EnabledTraceCategories": ["Aurora"]})

	def test_no_category_writes_the_engines_word_for_none(self):
		self.config.parent.mkdir()
		self.config.write_text(DEFAULTS)
		vigil_loop.Configure(self.config, None, 4747, "", [], 5)
		self.assertEqual(vigil_loop.ParseConfig(self.config.read_text())[1]["EnabledTraceCategories"], ["None"])

	def test_a_missing_file_and_no_editor_to_write_it_is_unanswered(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Configure(self.config, None, 4747, "", [], 5)
		self.assertEqual((raised.exception.status, raised.exception.failure), (vigil_loop.UNANSWERED, "config_unwritten"))

	def test_a_missing_file_is_seeded_by_the_editor_writing_its_defaults(self):
		vigil_loop.Configure(self.config, SeedingEditor(self._tmp.name), 4747, "capture.vigil", [], 30)
		self.assertEqual(vigil_loop.ParseConfig(self.config.read_text())[1]["CaptureFile"], "capture.vigil")

	def test_a_file_without_a_parcel_header_is_seeded_too(self):
		self.config.parent.mkdir()
		self.config.write_text("Enabled=true\nPort=4747\n")
		vigil_loop.Configure(self.config, SeedingEditor(self._tmp.name), 4747, "", [], 30)
		self.assertTrue(vigil_loop.ParseConfig(self.config.read_text())[1]["Enabled"])

	def test_a_parcel_of_other_fields_is_refused_untouched_and_no_editor_launched(self):
		self.config.parent.mkdir()
		changed = DEFAULTS + " 1 4 72 101 121 33"
		self.config.write_text(changed)
		marker = Path(self._tmp.name) / "launched"
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Configure(self.config, SeedingEditor(self._tmp.name, marker), 4747, "", [], 30)
		self.assertEqual((raised.exception.status, raised.exception.failure),
			(vigil_loop.UNRUNNABLE, "config_unrecognized"))
		self.assertEqual(self.config.read_text(), changed)
		self.assertFalse(marker.exists())

	def test_an_editor_that_leaves_no_readable_file_is_named_as_the_cause(self):
		editor = Path(self._tmp.name) / "editor.py"
		editor.write_text("")
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Configure(self.config, [sys.executable, str(editor)], 4747, "", [], 30)
		self.assertEqual(raised.exception.failure, "config_unwritten")
		self.assertIn("VigilAgent", str(raised.exception))

	def test_an_editor_that_never_exits_is_killed_and_named(self):
		editor = Path(self._tmp.name) / "editor.py"
		editor.write_text("import time\ntime.sleep(60)\n")
		started = time.monotonic()
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Configure(self.config, [sys.executable, str(editor)], 4747, "", [], 1)
		self.assertEqual(raised.exception.failure, "config_unwritten")
		self.assertLess(time.monotonic() - started, 30)


class RestoreTests(unittest.TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.config = Path(self._tmp.name) / "Configuration" / "Vigil.cfg"
		self.config.parent.mkdir()

	def tearDown(self):
		self._tmp.cleanup()

	def test_a_file_the_run_found_is_put_back_byte_for_byte(self):
		self.config.write_bytes(DEFAULTS.encode())
		snapshot = vigil_loop.SnapshotConfig(self.config)
		vigil_loop.Configure(self.config, None, 4848, "C:/work/capture.vigil", ["Aurora"], 5)
		self.assertTrue(vigil_loop.RestoreConfig(self.config, snapshot))
		self.assertEqual(self.config.read_bytes(), DEFAULTS.encode())

	def test_a_file_the_run_did_not_find_is_removed_again(self):
		snapshot = vigil_loop.SnapshotConfig(self.config)
		self.assertIsNone(snapshot)
		self.config.write_text(DEFAULTS)
		self.assertTrue(vigil_loop.RestoreConfig(self.config, snapshot))
		self.assertFalse(self.config.exists())


class CheckTests(unittest.TestCase):

	def test_the_check_is_held_to_the_repro_frames_when_they_are_known(self):
		arguments = vigil_loop.CheckArguments("c.vigil", [], ["PNG::Encode=50"], None, [129, 362])
		self.assertEqual(arguments, ["check", "c.vigil", "--json", "--frame-budget=PNG::Encode=50", "--frames=129:362"])

	def test_unknown_repro_frames_check_the_whole_capture(self):
		arguments = vigil_loop.CheckArguments("c.vigil", ["Engine::Cycle=2"], [], 0, None)
		self.assertEqual(arguments, ["check", "c.vigil", "--json", "--budget=Engine::Cycle=2", "--max-dropped-pulses=0"])

	def test_nothing_to_assert_runs_no_check(self):
		self.assertIsNone(vigil_loop.CheckArguments("c.vigil", [], [], None, [1, 2]))

	def test_the_repro_window_runs_from_after_the_frame_before_to_the_frame_after(self):
		self.assertEqual(vigil_loop.ReproWindow(128, 362), [129, 362])
		self.assertIsNone(vigil_loop.ReproWindow(None, 362))
		self.assertIsNone(vigil_loop.ReproWindow(362, 362))

	def test_a_failed_check_is_named_by_what_voids_the_most(self):
		self.assertEqual(vigil_loop.NameCheckFailure({"gaps_passed": False, "dropped_pulses_passed": False}), "gaps")
		self.assertEqual(vigil_loop.NameCheckFailure({"gaps_passed": True, "dropped_pulses_passed": False}),
			"pulses_dropped")
		self.assertEqual(vigil_loop.NameCheckFailure({"gaps_passed": True, "dropped_pulses_passed": True}),
			"budget_missed")


class ProcessTests(unittest.TestCase):

	def test_a_process_outliving_its_wait_is_killed(self):
		process = vigil_loop.Launch([sys.executable, "-c", "import time; time.sleep(60)"], "sleeper")
		self.assertIsNone(vigil_loop.Stop(process, 0.5))
		self.assertIsNotNone(process.poll())

	@unittest.skipIf(os.name == "nt", "a process group is POSIX; Windows kills the process alone")
	def test_a_kill_reaches_what_the_process_started(self):
		process = vigil_loop.Launch(["sh", "-c", "sleep 60 & echo $!; wait"], "shell", stdout=subprocess.PIPE, text=True)
		child = int(process.stdout.readline())
		vigil_loop.Kill(process)
		deadline = time.monotonic() + 10
		while time.monotonic() < deadline:
			try:
				os.kill(child, 0)
			except ProcessLookupError:
				return
			time.sleep(0.1)
		self.fail(f"the shell's child {child} outlived the kill")

	def test_a_command_that_does_not_exist_is_launch_failed(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Launch([str(Path(tempfile.gettempdir()) / "no-such-editor.exe")], "Editor")
		self.assertEqual((raised.exception.status, raised.exception.failure), (vigil_loop.UNRUNNABLE, "launch_failed"))


def RunMain(argv):
	output = io.StringIO()
	with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
		status = vigil_loop.Main(argv)
	return status, json.loads(output.getvalue())


class RunTests(unittest.TestCase):

	def test_an_editor_that_does_not_exist_is_refused_before_anything_is_written(self):
		with tempfile.TemporaryDirectory() as directory:
			editor = Path(directory) / "bin" / "editor.exe"
			status, summary = RunMain(["run", "--editor", str(editor), "--vigil", sys.executable,
				"--work", str(Path(directory) / "work"), "--category", "Aurora"])
			self.assertEqual((status, summary["failure"]), (vigil_loop.UNRUNNABLE, "launch_failed"))
			self.assertFalse((Path(directory) / "bin").exists())
			self.assertFalse((Path(directory) / "work").exists())

	@unittest.skipUnless(os.name == "nt", "only Windows refuses to remove a file another handle holds open")
	def test_a_capture_held_open_is_work_locked(self):
		with tempfile.TemporaryDirectory() as directory:
			work = Path(directory) / "work"
			work.mkdir()
			with (work / "capture.vigil").open("w"):
				status, summary = RunMain(["run", "--editor", sys.executable, "--vigil", sys.executable,
					"--work", str(work), "--category", "Aurora"])
			self.assertEqual((status, summary["failure"]), (vigil_loop.UNRUNNABLE, "work_locked"))


class EnvironmentTests(unittest.TestCase):

	def test_the_forge_lib_directory_beside_bin_leads_the_library_search_path(self):
		with tempfile.TemporaryDirectory() as directory:
			editor = Path(directory) / "bin" / "editor.exe"
			editor.parent.mkdir()
			(Path(directory) / "lib").mkdir()
			variable = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
			found = vigil_loop.EditorEnvironment(["xvfb-run", "-a", str(editor)])[variable]
			self.assertEqual(found.split(os.pathsep)[0], str((Path(directory) / "lib").resolve()))

	def test_no_lib_directory_leaves_the_environment_as_it_was(self):
		with tempfile.TemporaryDirectory() as directory:
			self.assertEqual(vigil_loop.EditorEnvironment([str(Path(directory) / "editor")]), dict(os.environ))


class AttachTests(unittest.TestCase):

	def Attach(self, answer):
		engine = StandInEngine(Frame(answer))
		try:
			return vigil_loop.Attach(engine.path, "Aurora", Running(), 5)
		finally:
			engine.Close()

	def test_an_enabled_category_returns_the_engines_answer(self):
		self.assertEqual(self.Attach("OK Aurora"), "OK Aurora")

	def test_a_command_closed_to_agents_means_profiling_is_inactive(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			self.Attach("ERR Command 'vigil.trace' is not available to agents")
		self.assertEqual((raised.exception.status, raised.exception.failure), (vigil_loop.UNANSWERED, "profiling_inactive"))

	def test_an_unknown_category_is_misuse_and_keeps_the_engines_list(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			self.Attach("ERR Unknown trace category 'Auroa'. Known categories: Aurora, Prism")
		self.assertEqual((raised.exception.status, raised.exception.failure), (vigil_loop.MISUSED, "unknown_category"))
		self.assertIn("Known categories: Aurora, Prism", str(raised.exception))

	def test_no_engine_within_the_wait_is_no_engine(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Attach(AbsentPipe(), "Aurora", Running(), 0.5)
		self.assertEqual((raised.exception.status, raised.exception.failure), (vigil_loop.UNANSWERED, "no_engine"))
		self.assertIn("no engine attached", str(raised.exception))

	def test_an_editor_that_exited_is_no_engine_and_says_with_what(self):
		with self.assertRaises(vigil_loop.LoopFailure) as raised:
			vigil_loop.Attach(AbsentPipe(), "Aurora", Exited(3), 30)
		self.assertEqual(raised.exception.failure, "no_engine")
		self.assertIn("exited with 3", str(raised.exception))


class EventTests(unittest.TestCase):

	def test_the_newest_frame_is_the_last_frame_event_and_bad_lines_are_skipped(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "monitor.ndjson"
			path.write_text('{"event":"listening","port":4747}\n{"event":"frame","frame":41}\nnot json\n'
				'{"event":"frame","frame":42}\n{"event":"disconnected"}\n')
			self.assertEqual(vigil_loop.NewestFrame(path), 42)
			self.assertIsNone(vigil_loop.NewestFrame(Path(directory) / "absent.ndjson"))

	def test_the_monitor_gap_frames_are_those_it_flagged(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "monitor.ndjson"
			path.write_text('{"event":"frame","frame":7,"gap":false}\n{"event":"frame","frame":8,"gap":true}\n'
				'{"event":"disconnected","gap":true}\n')
			self.assertEqual(vigil_loop.GapFrames(path), [8])


class ReproTests(unittest.TestCase):

	def test_the_repro_error_file_ends_the_wait_at_once_with_its_text(self):
		with tempfile.TemporaryDirectory() as directory:
			error = Path(directory) / ".capture-error"
			error.write_text("PNG encode failed")
			with self.assertRaises(vigil_loop.LoopFailure) as raised:
				vigil_loop.WaitForRepro(Path(directory) / ".last-capture", error, Running(), 30)
			self.assertEqual(raised.exception.failure, "repro_failed")
			self.assertIn("PNG encode failed", str(raised.exception))

	def test_the_signal_ends_the_wait(self):
		with tempfile.TemporaryDirectory() as directory:
			signal_path = Path(directory) / ".last-capture"
			signal_path.write_text("capture-001.png")
			vigil_loop.WaitForRepro(signal_path, Path(directory) / ".capture-error", Running(), 1)

	def test_no_signal_within_the_wait_is_unfinished(self):
		with tempfile.TemporaryDirectory() as directory:
			with self.assertRaises(vigil_loop.LoopFailure) as raised:
				vigil_loop.WaitForRepro(Path(directory) / ".last-capture", None, Running(), 0.3)
			self.assertEqual(raised.exception.failure, "repro_unfinished")


if __name__ == "__main__":
	unittest.main()
