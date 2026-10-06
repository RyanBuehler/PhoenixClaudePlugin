#!/usr/bin/env python3
"""Unit tests for scripts/console_pipe.py.

The framing is tested in memory. The transport is tested against a stand-in engine on the platform's
own channel -- an AF_UNIX socket beside the FIFO path on Linux, a named pipe on Windows -- because
what the script promises there is reaching a real listener, which a mock would not prove.
"""

import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "console_pipe.py"
SPEC = importlib.util.spec_from_file_location("console_pipe", SCRIPT)
console_pipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(console_pipe)


def Run(*args):
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False, timeout=60)


def Frame(payload):
	data = payload.encode("utf-8")
	return f"{len(data)}\n".encode("ascii") + data


def ReadAll(data):
	return console_pipe.ReadAnswer(io.BytesIO(data).read)


class FramingTests(unittest.TestCase):

	def test_a_request_opens_with_the_reply_header(self):
		self.assertEqual(console_pipe.ComposeRequest("vigil.trace Mosaic on"), b"--reply -- vigil.trace Mosaic on\n")

	def test_a_request_of_no_command_or_of_several_lines_is_refused(self):
		for command in ("", "   ", "help\nquit", "help\rquit"):
			with self.assertRaises(ValueError, msg=repr(command)):
				console_pipe.ComposeRequest(command)

	def test_an_answer_is_read_by_its_byte_count_and_keeps_its_newlines(self):
		self.assertEqual(ReadAll(Frame("OK first\nsecond")), "OK first\nsecond")

	def test_an_answer_cut_short_is_no_answer(self):
		with self.assertRaises(console_pipe.NoAnswer):
			ReadAll(b"12\nOK short")

	def test_an_answer_without_a_byte_count_is_no_answer(self):
		for data in (b"", b"\nOK", b"OK true\n", b"9" * 40 + b"\n"):
			with self.assertRaises(console_pipe.NoAnswer, msg=repr(data)):
				ReadAll(data)

	def test_only_an_ok_answer_counts_as_answered(self):
		self.assertEqual(console_pipe.ClassifyAnswer("OK"), console_pipe.ANSWERED)
		self.assertEqual(console_pipe.ClassifyAnswer("OK Mosaic"), console_pipe.ANSWERED)
		self.assertEqual(console_pipe.ClassifyAnswer("ERR Unknown trace category 'Nope'"), console_pipe.REFUSED)
		self.assertEqual(console_pipe.ClassifyAnswer("OKAY"), console_pipe.REFUSED)


class StandInEngine:
	"""Answers one request on the platform's console pipe channel, recording the line it received."""

	def __init__(self, answer):
		self.answer = answer
		self.received = None
		self._tmp = tempfile.TemporaryDirectory()
		if os.name == "nt":
			from multiprocessing.connection import Listener
			self.path = f"\\\\.\\pipe\\phoe-console-pipe-test-{os.getpid()}-{id(self)}"
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


class TransportTests(unittest.TestCase):

	def test_the_exit_statuses_are_numbered_as_the_vigil_verbs_number_theirs(self):
		self.assertEqual((console_pipe.ANSWERED, console_pipe.MISUSED, console_pipe.UNANSWERED), (0, 1, 2))

	def test_an_ok_answer_is_printed_and_exits_zero(self):
		engine = StandInEngine(Frame("OK Mosaic"))
		try:
			result = Run("send", "--pipe", engine.path, "--wait", "5", "--", "vigil.trace", "Mosaic", "on")
		finally:
			engine.Close()
		self.assertEqual(result.returncode, console_pipe.ANSWERED, result.stderr)
		self.assertEqual(result.stdout.strip(), "OK Mosaic")
		self.assertEqual(engine.received, b"--reply -- vigil.trace Mosaic on\n")

	def test_an_err_answer_is_printed_and_exits_three(self):
		engine = StandInEngine(Frame("ERR Command 'vigil.capture.start' is not available to agents"))
		try:
			result = Run("send", "--pipe", engine.path, "--wait", "5", "--", "vigil.capture.start")
		finally:
			engine.Close()
		self.assertEqual(result.returncode, console_pipe.REFUSED, result.stderr)
		self.assertIn("not available to agents", result.stdout)

	def test_no_engine_on_the_pipe_exits_two_and_says_so(self):
		if os.name == "nt":
			path = f"\\\\.\\pipe\\phoe-console-pipe-absent-{os.getpid()}"
		else:
			path = str(Path(tempfile.gettempdir()) / f"phoe-console-pipe-absent-{os.getpid()}.fifo")
		result = Run("send", "--pipe", path, "--wait", "0.5", "--", "help")
		self.assertEqual(result.returncode, console_pipe.UNANSWERED, result.stderr)
		self.assertIn("no engine is listening on the console pipe", result.stderr)
		self.assertEqual(result.stdout, "")

	@unittest.skipUnless(os.name == "nt", "only Windows requires a named pipe")
	def test_a_path_outside_the_pipe_namespace_is_misuse_on_windows(self):
		result = Run("send", "--pipe", "C:/tmp/phoenix.fifo", "--", "help")
		self.assertEqual(result.returncode, console_pipe.MISUSED, result.stderr)
		self.assertIn("named pipe", result.stderr)


if __name__ == "__main__":
	unittest.main()
