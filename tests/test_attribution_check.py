#!/usr/bin/env python3
"""Unit tests for hooks/attribution-check.py."""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "attribution-check.py"
spec = importlib.util.spec_from_file_location("attribution_check", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class AttributionCheckTestCase(unittest.TestCase):

	def _run_with_output(self, command):
		old_stdin = sys.stdin
		sys.stdin = io.StringIO(json.dumps({"tool_input": {"command": command}}))
		out = io.StringIO()
		code = 0
		try:
			with redirect_stdout(out), redirect_stderr(io.StringIO()):
				hook.main()
		except SystemExit as exit_value:
			code = exit_value.code
		finally:
			sys.stdin = old_stdin
		return code, out.getvalue()

	def _run(self, command):
		return self._run_with_output(command)[0]

	def test_commit_trailer_is_blocked(self):
		command = 'git commit -m "Fix it\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>"'
		self.assertEqual(self._run(command), 2)

	def test_git_dash_c_commit_is_blocked(self):
		command = 'git -C /repo commit -m "x\n\nCo-authored-by: Claude <noreply@anthropic.com>"'
		self.assertEqual(self._run(command), 2)

	def test_pr_banner_is_blocked(self):
		command = 'gh pr create --title T --body "Summary\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"'
		self.assertEqual(self._run(command), 2)

	def test_body_file_is_read(self):
		with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
			handle.write("Summary\n\nGenerated with Claude Code\n")
			path = handle.name
		try:
			self.assertEqual(self._run(f"gh pr create --title T --body-file {path}"), 2)
			self.assertEqual(self._run(f"gh pr edit 12 --body-file={path}"), 2)
			self.assertEqual(self._run(f"git commit -F {path}"), 2)
		finally:
			os.unlink(path)

	def test_clean_pr_passes(self):
		self.assertEqual(self._run('gh pr create --title T --body "Closes #4."'), 0)

	def test_human_coauthor_passes(self):
		command = 'git commit -m "x\n\nCo-Authored-By: Jane Doe <jane@example.com>"'
		self.assertEqual(self._run(command), 0)

	def test_read_only_audit_passes(self):
		command = 'git log origin/main..HEAD --format=%B | grep -ci "co-authored-by: claude"'
		self.assertEqual(self._run(command), 0)

	def test_missing_body_file_passes(self):
		self.assertEqual(self._run("gh pr create --body-file /nonexistent/body.md"), 0)

	def test_mentions_never_ask(self):
		for command in (
			'gh pr create --title T --body "Ported from the Claude draft"',
			'git commit -m "Match ChatGPT output"',
			'gh issue comment 3 --body "Docs: https://claude.com/x"',
			"git -C ~/phoenixclaudeplugin commit -m 'Ask Claude later'",
		):
			code, output = self._run_with_output(command)
			self.assertEqual((code, output.strip()), (0, "{}"), command)

	def test_claude_directory_cwd_and_paths_pass(self):
		for command in (
			"git -C /r/.claude/worktrees/a commit -m 'Fix the cull'",
			"git -C ~/phoenixclaudeplugin commit -m 'Bump version'",
			"gh pr create --title T --body-file /home/u/.claude/jobs/x/body.md",
			"git commit --file=/tmp/claude-msg.txt -m 'x'",
		):
			code, output = self._run_with_output(command)
			self.assertEqual((code, output.strip()), (0, "{}"), command)

	def test_cwd_under_claude_is_ignored(self):
		old_stdin = sys.stdin
		payload = {"tool_input": {"command": "git commit -m 'Fix it'"}, "cwd": "/r/.claude/worktrees/claude-x"}
		sys.stdin = io.StringIO(json.dumps(payload))
		out = io.StringIO()
		try:
			with redirect_stdout(out), redirect_stderr(io.StringIO()):
				hook.main()
		except SystemExit as exit_value:
			self.assertEqual(exit_value.code, 0)
		finally:
			sys.stdin = old_stdin
		self.assertEqual(out.getvalue().strip(), "{}")

	def test_attribution_beside_a_path_is_blocked(self):
		command = 'git -C ~/.claude/x commit -m "x\n\nCo-Authored-By: Claude <noreply@anthropic.com>"'
		self.assertEqual(self._run(command), 2)

	def test_unrelated_command_mentioning_claude_passes(self):
		self.assertEqual(self._run('ls ~/.claude && echo "claude"'), 0)


if __name__ == "__main__":
	unittest.main()
