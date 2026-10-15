#!/usr/bin/env python3
"""Unit tests for hooks/core-rules.py.

Every case runs the real script with a hook payload on stdin, the way Claude Code invokes it,
and reads the JSON it prints. The rules file is the real one, so the size check guards the
content as well as the hook.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "hooks" / "core-rules.py"
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"
CONTEXT_LIMIT = 10000


def Run(payload):
	stdin = payload if isinstance(payload, str) else json.dumps(payload)
	result = subprocess.run(
		[sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, check=False)
	return result.returncode, json.loads(result.stdout), result.stderr


def Context(output):
	return output.get("hookSpecificOutput", {}).get("additionalContext", "")


class CoreRulesTests(unittest.TestCase):

	def test_session_start_returns_the_rules_as_additional_context(self):
		code, output, _ = Run({"hook_event_name": "SessionStart", "source": "startup"})
		self.assertEqual(code, 0)
		self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
		self.assertIn("# Phoenix core rules", Context(output))

	def test_every_session_source_gets_the_rules(self):
		for source in ("startup", "resume", "clear", "compact", "fork"):
			with self.subTest(source=source):
				_, output, _ = Run({"hook_event_name": "SessionStart", "source": source})
				self.assertIn("# Phoenix core rules", Context(output))

	def test_the_rules_fit_under_the_context_limit(self):
		_, output, stderr = Run({"hook_event_name": "SessionStart", "source": "startup"})
		self.assertLess(len(Context(output)), CONTEXT_LIMIT)
		self.assertEqual(stderr, "")

	def test_the_plugin_root_placeholder_is_replaced_with_the_real_path(self):
		_, output, _ = Run({"hook_event_name": "SessionStart", "source": "startup"})
		self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", Context(output))
		self.assertIn(PLUGIN_ROOT.as_posix(), Context(output))

	def test_a_phoenix_subagent_gets_the_rules(self):
		for agent_type in ("phoe:invoke-code-reviewer", "general-purpose"):
			with self.subTest(agent_type=agent_type):
				_, output, _ = Run({"hook_event_name": "SubagentStart", "agent_type": agent_type})
				self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SubagentStart")
				self.assertIn("# Phoenix core rules", Context(output))

	def test_built_in_read_only_and_harness_agents_get_nothing(self):
		for agent_type in ("Explore", "Plan", "claude-code-guide", "statusline-setup"):
			with self.subTest(agent_type=agent_type):
				code, output, _ = Run({"hook_event_name": "SubagentStart", "agent_type": agent_type})
				self.assertEqual(code, 0)
				self.assertEqual(output, {})

	def test_unreadable_input_still_loads_the_rules_for_a_session(self):
		code, output, _ = Run("not json")
		self.assertEqual(code, 0)
		self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
		self.assertIn("# Phoenix core rules", Context(output))

	def test_hooks_json_wires_both_events_with_a_quoted_plugin_root(self):
		hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
		for event_name in ("SessionStart", "SubagentStart"):
			with self.subTest(event=event_name):
				commands = [hook["command"] for group in hooks[event_name] for hook in group["hooks"]]
				self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/core-rules.py"', commands)


if __name__ == "__main__":
	unittest.main()
