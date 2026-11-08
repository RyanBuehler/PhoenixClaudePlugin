#!/usr/bin/env python3
"""Unit tests for hooks/branch-worktree-check.py."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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
			"-b challenge/combined-saga-label"
		)
		self.assertEqual(code, 2)
		decision = json.loads(output)
		self.assertEqual(decision["decision"], "block")
		self.assertIn("path and branch do not match", decision["reason"])

	def test_registry_opt_in_unblocks_shortened_path(self):
		"""A registry file mapping basename→branch unblocks the shortened path."""
		self._seed_registry("short-name", "challenge/combined-saga-label")
		code, output = self._run(
			"git worktree add .claude/worktrees/short-name "
			"-b challenge/combined-saga-label"
		)
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")

	def test_registry_with_wrong_branch_still_blocks(self):
		"""Registry must record the EXACT branch — a mismatched entry blocks."""
		self._seed_registry("short-name", "challenge/some-other-label")
		code, _output = self._run(
			"git worktree add .claude/worktrees/short-name "
			"-b challenge/combined-saga-label"
		)
		self.assertEqual(code, 2)

	def test_strict_match_works_unchanged(self):
		"""Default basename == branch.replace('/','-') still passes."""
		code, output = self._run(
			"git worktree add .claude/worktrees/challenge-foo -b challenge/foo"
		)
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")


class TestPathsResolveAgainstMainCheckout(unittest.TestCase):
	"""The registry and the expected path are anchored at the main checkout,
	found from git, however the path is spelled and wherever the command runs."""

	BRANCH = "bug/x"
	FOLDER = "bug-x"
	LONG_BRANCH = "challenge/combined-saga-label"
	SHORT_FOLDER = "short-name"

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.root = os.path.realpath(self._tmp.name)
		self._git(self.root, "init", "-q")
		self._git(
			self.root, "-c", "user.name=t", "-c", "user.email=t@example.com",
			"commit", "-q", "--allow-empty", "-m", "base")
		self.worktree = os.path.join(self.root, ".claude", "worktrees", "bug-existing")
		self._git(self.root, "worktree", "add", "-q", self.worktree, "-b", "bug/existing")
		self.registry = Path(self.root) / hook.BRANCH_REGISTRY_DIR
		self.registry.mkdir(parents=True, exist_ok=True)

	@staticmethod
	def _git(cwd, *args):
		subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

	def _absolute(self, folder):
		return os.path.join(self.root, ".claude", "worktrees", folder)

	def _register(self):
		(self.registry / self.SHORT_FOLDER).write_text(self.LONG_BRANCH + "\n", encoding="utf-8")

	def _run(self, command, cwd):
		payload = json.dumps({"tool_input": {"command": command}, "cwd": cwd})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), redirect_stdout(out):
			try:
				hook.main()
			except SystemExit as exit_value:
				return exit_value.code, out.getvalue()
		return 0, out.getvalue()

	def assertAccepted(self, path, branch, cwd):
		code, output = self._run(f"git worktree add {path} -b {branch}", cwd)
		self.assertEqual((code, output.strip()), (0, "{}"), path)

	def assertRejected(self, path, branch, cwd):
		code, output = self._run(f"git worktree add {path} -b {branch}", cwd)
		self.assertEqual(code, 2, path)
		self.assertIn("path and branch do not match", json.loads(output)["reason"])

	def test_relative_expected_path_from_root(self):
		self.assertAccepted(".claude/worktrees/" + self.FOLDER, self.BRANCH, self.root)

	def test_absolute_expected_path_from_root(self):
		self.assertAccepted(self._absolute(self.FOLDER), self.BRANCH, self.root)

	def test_absolute_expected_path_from_worktree(self):
		self.assertAccepted(self._absolute(self.FOLDER), self.BRANCH, self.worktree)

	def test_relative_path_reaching_expected_location_from_worktree(self):
		self.assertAccepted("../" + self.FOLDER, self.BRANCH, self.worktree)

	def test_relative_path_that_would_nest_inside_a_worktree_is_rejected(self):
		self.assertRejected(".claude/worktrees/" + self.FOLDER, self.BRANCH, self.worktree)

	def test_absolute_path_with_wrong_folder_is_rejected(self):
		self.assertRejected(self._absolute("bug-y"), self.BRANCH, self.root)

	def test_absolute_path_outside_the_repository_is_rejected(self):
		self.assertRejected("/tmp/worktrees/" + self.FOLDER, self.BRANCH, self.root)

	def test_mismatch_names_the_main_checkout_location(self):
		_, output = self._run(f"git worktree add ../elsewhere -b {self.BRANCH}", self.worktree)
		reason = json.loads(output)["reason"]
		self.assertIn(self._absolute(self.FOLDER), reason)
		self.assertIn(str(self.registry), reason)

	def test_registry_from_root_relative_and_absolute(self):
		self._register()
		self.assertAccepted(".claude/worktrees/" + self.SHORT_FOLDER, self.LONG_BRANCH, self.root)
		self.assertAccepted(self._absolute(self.SHORT_FOLDER), self.LONG_BRANCH, self.root)

	def test_registry_from_worktree_relative_and_absolute(self):
		self._register()
		self.assertAccepted("../" + self.SHORT_FOLDER, self.LONG_BRANCH, self.worktree)
		self.assertAccepted(self._absolute(self.SHORT_FOLDER), self.LONG_BRANCH, self.worktree)

	def test_registry_is_read_from_main_checkout_not_the_worktree(self):
		stray = Path(self.worktree) / hook.BRANCH_REGISTRY_DIR
		stray.mkdir(parents=True)
		(stray / self.SHORT_FOLDER).write_text(self.LONG_BRANCH + "\n", encoding="utf-8")
		self.assertRejected(self._absolute(self.SHORT_FOLDER), self.LONG_BRANCH, self.worktree)

	def test_registry_does_not_admit_a_path_outside_the_worktrees_directory(self):
		self._register()
		self.assertRejected("/tmp/" + self.SHORT_FOLDER, self.LONG_BRANCH, self.root)


class TestForceBranchFastForward(HookTestCase):
	"""Regression guard for bug pretooluse-hook-blocks-legitimate-fast-forward-branch-update:
	`git branch -f <existing-branch> <commit>` should be allowed when the move
	is a true fast-forward (commit descends from current branch tip)."""

	def _patch_git(self, exists, is_ancestor):
		"""Make subprocess.run mimic `git rev-parse --verify` and `git merge-base --is-ancestor`."""
		def fake_run(cmd, capture_output, text, check):
			if cmd[:3] == ["git", "rev-parse", "--verify"]:
				class R: returncode = 0 if exists else 1
				return R()
			if cmd[:3] == ["git", "merge-base", "--is-ancestor"]:
				class R: returncode = 0 if is_ancestor else 1
				return R()
			class R: returncode = 0
			return R()
		return mock.patch.object(hook.subprocess, "run", side_effect=fake_run)

	def test_force_branch_fast_forward_allowed(self):
		"""`git branch -f existing main` allowed when main descends from existing."""
		with self._patch_git(exists=True, is_ancestor=True):
			code, output = self._run("git branch -f challenge/x main")
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")

	def test_force_branch_non_fast_forward_blocked(self):
		"""`git branch -f existing some-non-ancestor` still blocked."""
		with self._patch_git(exists=True, is_ancestor=False):
			code, _output = self._run("git branch -f challenge/x rewind-target")
		self.assertEqual(code, 2)

	def test_force_branch_new_branch_blocked(self):
		"""`git branch -f new-branch HEAD` (branch does not exist) still blocked."""
		with self._patch_git(exists=False, is_ancestor=False):
			code, _output = self._run("git branch -f challenge/new HEAD")
		self.assertEqual(code, 2)

	def test_force_branch_implicit_head_commit(self):
		"""`git branch -f existing` (no commit arg → HEAD) is allowed when FF."""
		with self._patch_git(exists=True, is_ancestor=True):
			code, output = self._run("git branch -f challenge/x")
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")



class TestNameLengthCap(HookTestCase):
	"""Branch and worktree folder names stay within MAX_NAME_LENGTH so Windows
	build paths stay under MAX_PATH."""

	LONG = "challenge/open-anchored-popups-inside-dock-leaves-as-popup-roots"

	def test_long_branch_blocked_with_suggestion(self):
		"""A worktree add with an over-long branch is blocked and names a short one."""
		folder = self.LONG.replace("/", "-")
		code, output = self._run(f"git worktree add .claude/worktrees/{folder} -b {self.LONG}")
		self.assertEqual(code, 2)
		self.assertIn("challenge/open-anchored-popups-inside", output)

	def test_branch_at_limit_allowed(self):
		"""A branch exactly MAX_NAME_LENGTH long passes with its matching path."""
		branch = "challenge/" + "a" * (hook.MAX_NAME_LENGTH - len("challenge/"))
		folder = branch.replace("/", "-")
		code, output = self._run(f"git worktree add .claude/worktrees/{folder} -b {branch} origin/main")
		self.assertEqual(code, 0)
		self.assertEqual(output.strip(), "{}")

	def test_long_branch_blocked_on_checkout(self):
		"""The length error wins over the use-a-worktree error on checkout -b."""
		code, output = self._run(f"git checkout -b {self.LONG}")
		self.assertEqual(code, 2)
		self.assertIn("the limit is", output)

	def test_long_folder_blocked_without_branch(self):
		"""A worktree add of an existing branch into a long folder is blocked."""
		code, _output = self._run(
			"git worktree add .claude/worktrees/" + "x" * (hook.MAX_NAME_LENGTH + 1) + " challenge/x")
		self.assertEqual(code, 2)

	def test_long_folder_blocked_on_move(self):
		"""Moving a worktree to a long folder is blocked; a short one passes."""
		long_target = ".claude/worktrees/" + "x" * (hook.MAX_NAME_LENGTH + 1)
		code, _output = self._run(f"git worktree move .claude/worktrees/a {long_target}")
		self.assertEqual(code, 2)
		code, _output = self._run("git worktree move .claude/worktrees/a .claude/worktrees/b")
		self.assertEqual(code, 0)

	def test_folder_outside_worktrees_unchecked(self):
		"""Only folders under .claude/worktrees/ are capped."""
		code, _output = self._run("git worktree add ../" + "x" * (hook.MAX_NAME_LENGTH + 1) + " main")
		self.assertEqual(code, 0)

	def test_short_branch_drops_trailing_filler(self):
		"""The cut keeps whole words and drops a trailing filler word."""
		self.assertEqual(
			hook.short_branch("challenge/give-2d-recording-segments-a-band-and-each-band-a-top-slot"),
			"challenge/give-2d-recording-segments")

	def test_short_branch_leaves_short_names(self):
		"""A name within the limit comes back unchanged."""
		self.assertEqual(hook.short_branch("bug/fix-focus"), "bug/fix-focus")

	def test_short_branch_cuts_one_long_word(self):
		"""A single word longer than the budget is cut hard."""
		result = hook.short_branch("bug/" + "y" * 60)
		self.assertEqual(len(result), hook.MAX_NAME_LENGTH)
		self.assertTrue(hook.BRANCH_RE.match(result))


if __name__ == "__main__":
	unittest.main()
