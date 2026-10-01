#!/usr/bin/env python3
"""Unit tests for scripts/forge_wait.py.

Every case runs real detached processes. What the script promises is process behavior — a run
outliving the call that started it, an exit status read back later — so a mock would prove nothing.
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "forge_wait.py"
STILL_RUNNING = 124
DIED = 125


def Run(*args):
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


class ForgeWaitTests(unittest.TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.log = str(Path(self._tmp.name) / "logs" / "run.log")

	def tearDown(self):
		self._tmp.cleanup()

	def test_a_finished_run_reports_its_exit_status_and_log(self):
		result = Run("start", "--log", self.log, "--", "sh", "-c", "echo hello; exit 3")
		self.assertEqual(result.returncode, 3, result.stdout)
		self.assertIn("exited 3", result.stdout)
		self.assertIn("hello", result.stdout)

	def test_a_run_outliving_the_timeout_is_resumed_by_wait(self):
		started = Run("start", "--log", self.log, "--timeout", "1", "--", "sh", "-c", "sleep 3; echo done")
		self.assertEqual(started.returncode, STILL_RUNNING, started.stdout)
		self.assertIn("still running", started.stdout)
		self.assertIn("wait --log", started.stdout)
		resumed = Run("wait", "--log", self.log, "--timeout", "20")
		self.assertEqual(resumed.returncode, 0, resumed.stdout)
		self.assertIn("done", resumed.stdout)

	def test_a_long_log_keeps_failed_lines_from_its_elided_middle(self):
		command = "seq 1 200; echo 'Build      FAILED  middle'; seq 1 200"
		result = Run("start", "--log", self.log, "--", "sh", "-c", command)
		self.assertEqual(result.returncode, 0, result.stdout)
		self.assertIn("lines elided", result.stdout)
		self.assertIn("Build      FAILED  middle", result.stdout)

	def test_a_run_that_vanished_without_an_exit_status_reads_as_died(self):
		Path(self.log).parent.mkdir(parents=True)
		Path(self.log).write_text("partial output\n")
		gone = subprocess.Popen(["true"])
		gone.wait()
		Path(f"{self.log}.pid").write_text(f"{gone.pid}\n")
		result = Run("wait", "--log", self.log, "--timeout", "5")
		self.assertEqual(result.returncode, DIED, result.stdout)
		self.assertIn("died", result.stdout)
		self.assertIn("partial output", result.stdout)

	def test_start_refuses_a_log_that_a_live_run_still_owns(self):
		first = Run("start", "--log", self.log, "--timeout", "0", "--", "sleep", "3")
		self.assertEqual(first.returncode, STILL_RUNNING, first.stdout)
		second = Run("start", "--log", self.log, "--timeout", "0", "--", "true")
		self.assertEqual(second.returncode, 2, second.stdout)
		self.assertIn("already belongs", second.stdout)
		Run("wait", "--log", self.log, "--timeout", "20")

	def test_a_finished_run_can_be_restarted_on_the_same_log(self):
		Run("start", "--log", self.log, "--", "sh", "-c", "exit 1")
		again = Run("start", "--log", self.log, "--", "sh", "-c", "echo second")
		self.assertEqual(again.returncode, 0, again.stdout)
		self.assertIn("second", again.stdout)


if __name__ == "__main__":
	unittest.main()
