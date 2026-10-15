#!/usr/bin/env python3
"""SessionStart and SubagentStart hook: load the plugin's core rules into context.

A CLAUDE.md at a plugin's root is never loaded, so the always-on rules live in
references/core-rules.md and this hook returns them as `additionalContext`. SessionStart
runs on startup, resume, /clear and compaction, so the rules come back after each;
SubagentStart puts them at the head of each subagent's conversation.

The built-in Explore and Plan agents skip project instructions by design, and the
harness-help agents do no Phoenix work, so those receive nothing. `${CLAUDE_PLUGIN_ROOT}`
in the rules is replaced with the real plugin path, since hook text is not expanded.
A missing rules file never blocks a session: the hook warns on stderr and adds nothing.
"""

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PLUGIN_ROOT / "references" / "core-rules.md"
ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"

# Claude Code moves a longer additionalContext into a file and shows only a preview.
CONTEXT_LIMIT = 10000

SKIPPED_AGENT_TYPES = frozenset({"Explore", "Plan", "claude-code-guide", "statusline-setup"})


def ReadEvent():
	"""The hook input, or an empty event when stdin carries no JSON object."""
	try:
		data = json.load(sys.stdin)
	except (json.JSONDecodeError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}


def LoadRules():
	"""The rules text with plugin paths made absolute, or None when the file is unreadable."""
	try:
		text = RULES_PATH.read_text(encoding="utf-8")
	except OSError as error:
		print(f"core-rules: cannot read {RULES_PATH}: {error}", file=sys.stderr)
		return None
	return text.replace(ROOT_PLACEHOLDER, PLUGIN_ROOT.as_posix())


def Main():
	event = ReadEvent()
	event_name = event.get("hook_event_name") or "SessionStart"
	if event_name == "SubagentStart" and event.get("agent_type") in SKIPPED_AGENT_TYPES:
		print("{}")
		return 0
	rules = LoadRules()
	if rules is None:
		print("{}")
		return 0
	if len(rules) > CONTEXT_LIMIT:
		print(f"core-rules: {len(rules)} characters exceeds the {CONTEXT_LIMIT} limit", file=sys.stderr)
	output = {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": rules}}
	print(json.dumps(output))
	return 0


if __name__ == "__main__":
	sys.exit(Main())
