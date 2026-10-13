#!/usr/bin/env python3
"""Unit tests for hooks/push-gate.py."""

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "push-gate.py"
spec = importlib.util.spec_from_file_location("push_gate", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _completed(returncode=0, stdout="", stderr=""):
	return subprocess.CompletedProcess([], returncode, stdout, stderr)


class PushGateTests(unittest.TestCase):
	def _run(self, command, identity=True, auth=True):
		def fake_run(argv, **kwargs):
			if argv[:2] == ["git", "config"]:
				return _completed(stdout="value\n" if identity else "")
			if argv[:2] == ["git", "ls-remote"]:
				return _completed(0 if auth else 128, stderr="" if auth else "denied")
			raise AssertionError(argv)

		payload = json.dumps({"tool_input": {"command": command}})
		out = io.StringIO()
		with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
				mock.patch.object(hook.subprocess, "run", side_effect=fake_run), \
				redirect_stdout(out):
			with self.assertRaises(SystemExit):
				hook.main()
		return json.loads(out.getvalue()).get("hookSpecificOutput", {})

	def test_allows_git_push(self):
		self.assertEqual(self._run("git push origin main")["permissionDecision"], "allow")

	def test_allows_pr_create(self):
		self.assertEqual(self._run("gh pr create --draft")["permissionDecision"], "allow")

	def test_allows_inside_chain(self):
		self.assertEqual(self._run("git commit -m x && git push")["permissionDecision"], "allow")

	def test_denies_without_identity(self):
		self.assertEqual(self._run("git push", identity=False)["permissionDecision"], "deny")

	def test_denies_when_auth_fails(self):
		decision = self._run("git push", auth=False)
		self.assertEqual(decision["permissionDecision"], "deny")
		self.assertIn("denied", decision["permissionDecisionReason"])

	def test_ignores_dry_run(self):
		self.assertEqual(self._run("git push --dry-run"), {})

	def test_ignores_other_commands(self):
		self.assertEqual(self._run("git status"), {})
		self.assertEqual(self._run("gh pr view 12"), {})

	def test_uses_named_remote(self):
		seen = []
		real = hook.authenticates
		with mock.patch.object(hook, "authenticates", side_effect=lambda r: (seen.append(r), (True, ""))[1]):
			self._run("git push upstream main")
		self.assertEqual(seen, ["upstream"])


if __name__ == "__main__":
	unittest.main()
