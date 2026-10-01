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

	def _asks(self, command):
		code, output = self._run_with_output(command)
		self.assertEqual(code, 0)
		decision = json.loads(output).get("hookSpecificOutput", {}).get("permissionDecision")
		return decision == "ask"

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

	def test_assistant_mentions_ask(self):
		self.assertTrue(self._asks('gh pr create --title T --body "Ported from the Claude draft"'))
		self.assertTrue(self._asks('git commit -m "Match ChatGPT output"'))
		self.assertTrue(self._asks('gh issue comment 3 --body "chat-gpt said so"'))
		self.assertTrue(self._asks('git commit -m "Codex review notes"'))

	def test_mention_in_body_file_asks(self):
		with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
			handle.write("Reviewed with codex.\n")
			path = handle.name
		try:
			self.assertTrue(self._asks(f"gh pr create --title T --body-file {path}"))
		finally:
			os.unlink(path)

	def test_claude_directory_path_does_not_ask(self):
		with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
			handle.write("Closes #4.\n")
			path = handle.name
		try:
			command = f"gh pr create --title T --body-file /home/u/.claude/jobs/x/body.md --body-file {path}"
			self.assertFalse(self._asks(command))
			self.assertFalse(self._asks("git -C /r/.claude/worktrees/a commit -m 'Fix the cull'"))
		finally:
			os.unlink(path)

	def test_unrelated_command_mentioning_claude_passes(self):
		self.assertFalse(self._asks('ls ~/.claude && echo "claude"'))


if __name__ == "__main__":
	unittest.main()
