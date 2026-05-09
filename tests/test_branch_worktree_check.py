#!/usr/bin/env python3
"""Unit tests for hooks/branch-worktree-check.py."""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "branch-worktree-check.py"
spec = importlib.util.spec_from_file_location("branch_worktree_check", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _stdin_with(command):
	return io.StringIO(json.dumps({"tool_input": {"command": command}}))


class HookTestCase(unittest.TestCase):
	"""Base — runs each test in a temp cwd so registry files are scoped."""

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self._original_cwd = os.getcwd()
		os.chdir(self._tmp.name)

	def tearDown(self):
		os.chdir(self._original_cwd)
		self._tmp.cleanup()

	def _run(self, command):
		old_stdin = sys.stdin
		sys.stdin = _stdin_with(command)
		out = io.StringIO()
		try:
			with redirect_stdout(out):
				hook.main()
		except SystemExit as exit_value:
			return exit_value.code, out.getvalue()
		finally:
			sys.stdin = old_stdin
		return 0, out.getvalue()


class TestRedirectAndPipeTokensIgnored(HookTestCase):
	"""Regression guard for the SEPARATOR / REDIRECT_RE leakage that used to
	misclassify `2>&1` as a branch name."""

	def test_pipe_with_redirect_does_not_block_git_branch_a(self):
		"""`git branch -a 2>&1 | grep main` must pass — read-only listing."""
		code, output = self._run("git branch -a 2>&1 | grep main")
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")

	def test_git_branch_a_alone_does_not_block(self):
		"""`git branch -a` is a list flag, not a create."""
		code, output = self._run("git branch -a")
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")


class TestRegistryOverride(HookTestCase):
	"""Regression guard for bug branch-worktree-hook-mishandles-redirects part 2:
	the strict basename↔branch match used to reject any shortened or combined
	path even when the user explicitly wanted that mapping."""

	def _seed_registry(self, basename, branch):
		registry = Path(hook.BRANCH_REGISTRY_DIR)
		registry.mkdir(parents=True, exist_ok=True)
		(registry / basename).write_text(branch + "\n", encoding="utf-8")

	def test_strict_match_still_blocks_without_registry(self):
		"""Default behaviour preserved when no opt-in marker is present."""
		code, output = self._run(
			"git worktree add .claude/worktrees/short-name "
			"-b challenge/very-long-label-that-exceeds-comfort"
		)
		self.assertEqual(code, 2)
		decision = json.loads(output)
		self.assertEqual(decision["decision"], "block")
		self.assertIn("path and branch do not match", decision["reason"])

	def test_registry_opt_in_unblocks_shortened_path(self):
		"""A registry file mapping basename→branch unblocks the shortened path."""
		self._seed_registry("short-name", "challenge/very-long-label-that-exceeds-comfort")
		code, output = self._run(
			"git worktree add .claude/worktrees/short-name "
			"-b challenge/very-long-label-that-exceeds-comfort"
		)
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")

	def test_registry_with_wrong_branch_still_blocks(self):
		"""Registry must record the EXACT branch — a mismatched entry blocks."""
		self._seed_registry("short-name", "challenge/some-other-label")
		code, _output = self._run(
			"git worktree add .claude/worktrees/short-name "
			"-b challenge/very-long-label-that-exceeds-comfort"
		)
		self.assertEqual(code, 2)

	def test_strict_match_works_unchanged(self):
		"""Default basename == branch.replace('/','-') still passes."""
		code, output = self._run(
			"git worktree add .claude/worktrees/challenge-foo -b challenge/foo"
		)
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")


if __name__ == "__main__":
	unittest.main()
