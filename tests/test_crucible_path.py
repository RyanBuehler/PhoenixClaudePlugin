#!/usr/bin/env python3
"""Unit tests for scripts/crucible_path.py."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crucible_path.py"


def Run(root):
	return subprocess.run(
		[sys.executable, str(SCRIPT), "--root", str(root)],
		capture_output=True, text=True, check=False)


class CruciblePathTests(unittest.TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.root = Path(self._tmp.name)

	def tearDown(self):
		self._tmp.cleanup()

	def Place(self, relative, age_seconds=0):
		path = self.root / relative
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text("")
		stamp = time.time() - age_seconds
		os.utime(path, (stamp, stamp))
		return path

	def test_finds_a_windows_binary(self):
		expected = self.Place("Applications/Forge/.forge/crucible-windows/bin/crucible.exe")
		result = Run(self.root)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertEqual(result.stdout.strip(), expected.as_posix())

	def test_the_newest_copy_wins_across_build_trees(self):
		self.Place("Applications/Forge/.forge-out/crucible/bin/crucible", age_seconds=600)
		expected = self.Place("Applications/Forge/.forge/crucible-linux/bin/crucible")
		result = Run(self.root)
		self.assertEqual(result.stdout.strip(), expected.as_posix())

	def test_ignores_the_server_and_binaries_outside_bin(self):
		self.Place("Applications/Forge/.forge/crucible/bin/crucible-server")
		self.Place("Applications/Forge/.forge/crucible/obj/crucible")
		result = Run(self.root)
		self.assertEqual(result.returncode, 1)
		self.assertIn("run /phoe:build crucible", result.stderr)

	def test_reports_a_missing_build_tree(self):
		result = Run(self.root)
		self.assertEqual(result.returncode, 1)
		self.assertEqual(result.stdout, "")


if __name__ == "__main__":
	unittest.main()
