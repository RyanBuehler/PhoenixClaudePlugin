#!/usr/bin/env python3
"""Unit tests for hooks/branch-cleanup-allow.py."""

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "branch-cleanup-allow.py"
spec = importlib.util.spec_from_file_location("branch_cleanup_allow", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class BranchCleanupAllowTests(unittest.TestCase):
	def _run(self, command, pushed=True, open_pr=False):
		def fake_run(argv, **kwargs):
			if argv[:2] == ["git", "rev-parse"]:
				return subprocess.CompletedProcess(argv, 0, "abc123\n", "")
			if argv[:2] == ["git", "branch"]:
				return subprocess.CompletedProcess(argv, 0, "  origin/x\n" if pushed else "", "")
			if argv[:2] == ["gh", "pr"]:
				return subprocess.CompletedProcess(argv, 0, "1\n" if open_pr else "0\n", "")
			raise AssertionError(argv)

		payload = json.dumps({"tool_input": {"command": command}})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
				mock.patch.object(hook.subprocess, "run", side_effect=fake_run), \
				redirect_stdout(out):
			with self.assertRaises(SystemExit):
				hook.main()
		return json.loads(out.getvalue()).get("hookSpecificOutput", {}).get("permissionDecision")

	def test_allows_local_delete(self):
		self.assertEqual(self._run("git branch -D challenge/fix-thing"), "allow")
		self.assertEqual(self._run("git branch -d bug/windows-liaison-fix-focus"), "allow")

	def test_allows_remote_delete_forms(self):
		self.assertEqual(self._run("git push origin --delete challenge/fix-thing"), "allow")
		self.assertEqual(self._run("git push origin :challenge/fix-thing"), "allow")

	def test_allows_chained_cleanup_and_git_dash_c(self):
		command = "git -C /repo branch -D doc/x && git -C /repo push origin --delete doc/x"
		self.assertEqual(self._run(command), "allow")

	def test_falls_through_for_protected_or_unnamed_branches(self):
		for command in (
			"git branch -D main",
			"git push origin --delete main",
			"git push origin :main",
			"git branch -D feature",
			"git branch -D challenge/*",
			"git push origin --delete 'challenge/*'",
		):
			self.assertIsNone(self._run(command), command)

	def test_falls_through_when_chained_with_other_commands(self):
		self.assertIsNone(self._run("git branch -D bug/x && rm -rf build"))

	def test_local_delete_of_unpushed_branch_falls_through(self):
		self.assertIsNone(self._run("git branch -D bug/x", pushed=False))

	def test_remote_delete_with_open_pr_falls_through(self):
		self.assertIsNone(self._run("git push origin --delete bug/x", open_pr=True))
		self.assertIsNone(self._run("git push origin :bug/x", open_pr=True))

	def test_failed_check_falls_through(self):
		payload = json.dumps({"tool_input": {"command": "git push origin --delete bug/x"}})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
				mock.patch.object(hook.subprocess, "run", side_effect=OSError), \
				redirect_stdout(out):
			with self.assertRaises(SystemExit):
				hook.main()
		self.assertEqual(json.loads(out.getvalue()), {})

	def test_falls_through_for_non_deletes(self):
		for command in ("git branch bug/x", "git push origin bug/x", "git push --force origin :bug/x"):
			self.assertIsNone(self._run(command), command)


if __name__ == "__main__":
	unittest.main()
