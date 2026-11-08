#!/usr/bin/env python3
"""Unit tests for hooks/bash-guard.py."""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "bash-guard.py"
spec = importlib.util.spec_from_file_location("bash_guard", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class BashGuardTestCase(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.cwd = self._tmp.name

	def tearDown(self):
		self._tmp.cleanup()

	def _make_swept_dirs(self):
		os.makedirs(os.path.join(self.cwd, ".claude", "worktrees"))

	def _run(self, command):
		payload = json.dumps({"tool_input": {"command": command}, "cwd": self.cwd})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), redirect_stdout(out):
			with self.assertRaises(SystemExit):
				hook.main()
		text = out.getvalue()
		return json.loads(text).get("hookSpecificOutput", {}).get("permissionDecision")

	def assertDenied(self, command):
		self.assertEqual(self._run(command), "deny", command)

	def assertAllowed(self, command):
		self.assertIsNone(self._run(command), command)


class CdGitTests(BashGuardTestCase):
	def test_denies_cd_then_git(self):
		self.assertDenied("cd /tmp/x && git status")

	def test_denial_keeps_the_existing_message(self):
		payload = json.dumps({"tool_input": {"command": "cd /tmp/x && git status"}, "cwd": self.cwd})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), redirect_stdout(out):
			with self.assertRaises(SystemExit):
				hook.main()
		self.assertEqual(
			json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecisionReason"], hook.MSG_CD_GIT)

	def test_allows_git_before_cd(self):
		self.assertAllowed("git status; cd /tmp/x")

	def test_denies_git_on_both_sides_of_cd(self):
		self.assertDenied("git status; cd /tmp/x; git log")

	def test_denies_subshell(self):
		self.assertDenied("(cd /tmp/x && git log)")

	def test_denies_pushd_then_git(self):
		self.assertDenied("pushd /tmp/x && git log")

	def test_allows_cd_then_git_dash_c_absolute(self):
		self.assertAllowed("cd /tmp && git -C /home/ryan/phoenix status")

	def test_allows_absolute_dash_c_after_other_global_options(self):
		self.assertAllowed("cd /tmp && git -c core.pager=cat -C /home/ryan/phoenix log -1")

	def test_denies_cd_then_git_dash_c_relative(self):
		self.assertDenied("cd /tmp/x && git -C sub status")

	def test_denies_cd_then_dash_c_that_is_a_subcommand_flag(self):
		self.assertDenied("cd /tmp/x && git log -C /home/ryan/phoenix")

	def test_denies_cd_then_config_value_that_looks_like_dash_c(self):
		self.assertDenied("cd /tmp/x && git -c -C /home/ryan/phoenix status")

	def test_allows_git_dash_c(self):
		self.assertAllowed("git -C /tmp/x status")

	def test_allows_cd_with_non_git(self):
		self.assertAllowed("cd /tmp/x && forge build editor-debug")

	def test_allows_cd_inside_quoted_message(self):
		self.assertAllowed("echo 'cd here and git there'")


class QuotedSeparatorTests(BashGuardTestCase):
	def test_single_quoted_semicolon_does_not_split(self):
		self.assertAllowed("grep -e 'a; cd x' file.txt && git -C /home/ryan/phoenix log -1")
		self.assertAllowed("grep -e 'a; cd x' file.txt && git log -1")

	def test_separators_inside_quotes_do_not_fake_a_cd(self):
		self.assertAllowed("grep -e 'a; cd x; b' file.txt && git log -1")
		self.assertAllowed('grep "a | cd x | b" file.txt && git log -1')

	def test_double_quoted_pipe_does_not_split(self):
		self.assertAllowed('grep "a | cd x" file.txt && git log -1')

	def test_quoted_and_chain_does_not_split(self):
		self.assertAllowed("echo 'x && cd y' && git status")

	def test_quoted_newline_does_not_split(self):
		self.assertAllowed("python3 -c 'a = 1\ncd = 2' && git status")

	def test_escaped_quote_does_not_end_double_quotes(self):
		self.assertAllowed('echo "a \\" ; cd x" && git status')

	def test_escaped_separator_does_not_split(self):
		self.assertAllowed("echo a \\; cd x && git status")

	def test_quoted_git_after_cd_is_not_a_command(self):
		self.assertAllowed("cd /tmp/x && echo 'a; git status'")

	def test_unquoted_separators_still_split(self):
		self.assertDenied("echo 'a' ; cd /tmp/x ; git status")
		self.assertDenied("echo 'a' | cd /tmp/x | git status")
		self.assertDenied("cd /tmp/x\ngit status")

	def test_line_continuation_joins_the_command(self):
		self.assertDenied("cd /tmp/x && git \\\n  status")

	def test_comment_apostrophes_do_not_hide_commands(self):
		self.assertDenied("# don't\ncd /tmp/x && git status # won't")

	def test_unbalanced_quote_still_splits(self):
		self.assertDenied("cat notes <<EOF\nit's\nEOF\ncd /tmp/x && git status")

	def test_quoted_separator_does_not_hide_a_git_grep_chain(self):
		self.assertDenied("git grep 'a;b' && git grep c")
		self.assertAllowed("git grep 'a && b'")


class LoadTests(BashGuardTestCase):
	def test_denies_stress(self):
		self.assertDenied("stress-ng --cpu 8 --timeout 60")

	def test_denies_spinner(self):
		self.assertDenied("while :; do :; done")
		self.assertDenied("while true; do :; done")

	def test_denies_fork_bomb(self):
		self.assertDenied(":(){ :|:& };:")

	def test_denies_yes_to_devnull(self):
		self.assertDenied("yes > /dev/null")

	def test_denies_disk_filler(self):
		self.assertDenied("dd if=/dev/zero of=/tmp/fill bs=1M count=100000")

	def test_allows_dd_to_devnull(self):
		self.assertAllowed("dd if=/dev/zero of=/dev/null count=1")

	def test_denies_oversubscribed_jobs(self):
		with mock.patch.object(hook.os, "cpu_count", return_value=8):
			self.assertDenied("ninja -j 64")
			self.assertDenied("make -j64")
			self.assertDenied("forge build --parallel=99 editor-debug")

	def test_allows_jobs_within_cpus(self):
		with mock.patch.object(hook.os, "cpu_count", return_value=8):
			self.assertAllowed("ninja -j 8")
			self.assertAllowed("make -j4")


class SweepTests(BashGuardTestCase):
	def test_denies_recursive_grep_from_root(self):
		self._make_swept_dirs()
		self.assertDenied("grep -rn Symbol .")
		self.assertDenied("grep -r Symbol")

	def test_denies_find_from_root(self):
		self._make_swept_dirs()
		self.assertDenied("find . -name '*.cppm'")

	def test_allows_sweep_with_all_excludes(self):
		self._make_swept_dirs()
		self.assertAllowed("grep -rn Symbol . --exclude-dir={.forge*,.bootstrap-out,worktrees}")

	def test_allows_scoped_path(self):
		self._make_swept_dirs()
		self.assertAllowed("grep -rn Symbol Engine/Core")
		self.assertAllowed("find Engine -name '*.cppm'")

	def test_allows_sweep_where_nothing_to_sweep(self):
		self.assertAllowed("grep -rn Symbol .")

	def test_allows_non_recursive_grep(self):
		self._make_swept_dirs()
		self.assertAllowed("grep -n Symbol file.txt")


class GitGrepTests(BashGuardTestCase):
	def test_denies_context_flag_after_pattern(self):
		self.assertDenied("git grep Symbol -A3")

	def test_allows_context_flag_before_pattern(self):
		self.assertAllowed("git grep -A3 Symbol")

	def test_denies_include(self):
		self.assertDenied("git grep --include='*.cppm' Symbol")

	def test_denies_and_chained_greps(self):
		self.assertDenied("git grep A && git grep B")

	def test_allows_semicolon_chained_greps(self):
		self.assertAllowed("git grep A; git grep B")

	def test_allows_plain_grep(self):
		self.assertAllowed("git grep -n Symbol -- '*.cppm'")


if __name__ == "__main__":
	unittest.main()
