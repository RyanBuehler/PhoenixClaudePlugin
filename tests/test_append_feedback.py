#!/usr/bin/env python3
"""Unit tests for scripts/append_feedback.py.

Every case runs the real script, and the worktree case runs it inside a real git worktree: what the
script promises is where the entry lands and that earlier entries survive.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "append_feedback.py"


def Run(*args, stdin="", cwd=None):
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True,
		check=False, cwd=cwd)


def Git(*args, cwd):
	subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class AppendFeedbackTests(unittest.TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.root = Path(self._tmp.name)
		self.log = self.root / "logs" / "AGENT_FEEDBACK.md"

	def tearDown(self):
		self._tmp.cleanup()

	def test_creates_the_log_with_a_dated_heading(self):
		result = Run("--run", "/phoe:implement foo", "--log", str(self.log), "--date", "2026-10-15",
			stdin="### Implementer\n- slow build\n")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertEqual(
			self.log.read_bytes().decode(), "## 2026-10-15 - /phoe:implement foo\n\n### Implementer\n- slow build\n")

	def test_appends_after_earlier_entries_without_touching_them(self):
		self.log.parent.mkdir(parents=True)
		self.log.write_bytes(b"# Agent feedback\n\n## 2026-01-01 - /phoe:execute 2\n\n- old item\n")
		result = Run("--run", "/phoe:execute 3", "--log", str(self.log), "--date", "2026-10-15",
			stdin="### Orchestrator\n- new item\n")
		self.assertEqual(result.returncode, 0, result.stderr)
		text = self.log.read_bytes().decode()
		self.assertTrue(text.startswith("# Agent feedback\n\n## 2026-01-01 - /phoe:execute 2\n\n- old item\n"))
		self.assertIn("- old item\n\n## 2026-10-15 - /phoe:execute 3\n\n### Orchestrator\n- new item\n", text)

	def test_a_log_without_a_trailing_newline_still_gets_a_blank_line(self):
		self.log.parent.mkdir(parents=True)
		self.log.write_bytes(b"- old item")
		Run("--run", "/phoe:bugfix bar", "--log", str(self.log), "--date", "2026-10-15", stdin="- item\n")
		self.assertEqual(self.log.read_bytes().decode(), "- old item\n\n## 2026-10-15 - /phoe:bugfix bar\n\n- item\n")

	def test_a_blank_entry_writes_nothing(self):
		result = Run("--run", "/phoe:execute 1", "--log", str(self.log), stdin="\n  \n")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("nothing to append", result.stdout)
		self.assertFalse(self.log.exists())

	def test_reads_the_entry_from_a_file(self):
		entry = self.root / "entry.md"
		entry.write_bytes(b"### Orchestrator\n- from a file\n")
		Run("--run", "/phoe:execute 1", "--log", str(self.log), "--date", "2026-10-15", str(entry))
		self.assertIn("- from a file\n", self.log.read_bytes().decode())

	def test_from_a_worktree_the_entry_lands_in_the_main_checkout(self):
		main = self.root / "main"
		main.mkdir()
		Git("init", "-q", cwd=main)
		Git("-c", "user.name=Test", "-c", "user.email=test@example.com",
			"commit", "-q", "--allow-empty", "-m", "init", cwd=main)
		worktree = self.root / "wt"
		Git("worktree", "add", "-q", str(worktree), "-b", "challenge/x", cwd=main)
		result = Run("--run", "/phoe:implement x", stdin="- item\n", cwd=worktree)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertTrue((main / ".claude" / "AGENT_FEEDBACK.md").exists())
		self.assertFalse((worktree / ".claude" / "AGENT_FEEDBACK.md").exists())


if __name__ == "__main__":
	unittest.main()
