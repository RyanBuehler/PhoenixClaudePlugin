#!/usr/bin/env python3
"""PreToolUse hook: police AI-assistant text in git/gh commands that publish.

Claude attribution is refused outright: the harness settings are already off, so
any trailer or banner is typed by habit, and a squash merge copies a branch
commit's trailers into main. Any other mention of an assistant asks the user.
"""

import json
import re
import shlex
import sys

ATTRIBUTION_RE = re.compile(
	r"co-authored-by:[^\n]*(claude|anthropic)"
	r"|generated (with|by) \[?claude"
	r"|\U0001F916 generated",
	re.IGNORECASE,
)

MENTION_RE = re.compile(r"claude|chat[\s_-]*gpt|codex", re.IGNORECASE)

# `.claude/` paths (job tmp dirs, worktrees) name a directory, not an assistant.
CLAUDE_PATH_RE = re.compile(r"[^\s\"']*\.claude/[^\s\"']*")

# Only commands that write text somewhere durable are checked, so a read-only
# `git log | grep "Co-Authored-By: Claude"` audit still runs.
PUBLISHING_RE = re.compile(
	r"\bgit\s+(?:-C\s+\S+\s+)?(commit|tag|notes|merge)\b"
	r"|\bgh\s+(pr|issue|release|api)\b"
)

BODY_FILE_FLAGS = {"-F", "--file", "--body-file", "--notes-file", "--input"}

MSG_BLOCKED = (
	"Claude attribution found in {where}: '{match}'.\n"
	"Never add Co-Authored-By Claude trailers or 'Generated with Claude Code'\n"
	"banners to commits, PR/issue bodies, comments, tags, or releases.\n"
	"Remove it and re-run the command."
)


def body_files(command):
	"""Paths passed to a file-body flag, read so `--body-file` is not a bypass."""
	try:
		tokens = shlex.split(command)
	except ValueError:
		return []
	paths = []
	for index, token in enumerate(tokens):
		flag, _, value = token.partition("=")
		if flag not in BODY_FILE_FLAGS:
			continue
		if not value and index + 1 < len(tokens):
			value = tokens[index + 1]
		if value and value != "-":
			paths.append(value)
	return paths


def ask(where, match):
	reason = (
		f"This command publishes text that mentions an AI assistant ('{match}' in {where}).\n"
		"Confirm with the user before it goes out."
	)
	print(json.dumps({"hookSpecificOutput": {
		"hookEventName": "PreToolUse",
		"permissionDecision": "ask",
		"permissionDecisionReason": reason,
	}}))
	sys.exit(0)


def block(where, match):
	print(MSG_BLOCKED.format(where=where, match=match), file=sys.stderr)
	sys.exit(2)


def main():
	data = json.load(sys.stdin)
	command = data.get("tool_input", {}).get("command", "")
	if not PUBLISHING_RE.search(command):
		print("{}")
		sys.exit(0)
	texts = [("the command text", command)]
	for path in body_files(command):
		try:
			with open(path, "r", encoding="utf-8", errors="replace") as handle:
				texts.append((path, handle.read()))
		except OSError:
			continue
	for where, text in texts:
		found = ATTRIBUTION_RE.search(text)
		if found:
			block(where, found.group(0))
	for where, text in texts:
		found = MENTION_RE.search(CLAUDE_PATH_RE.sub("", text))
		if found:
			ask(where, found.group(0))
	print("{}")
	sys.exit(0)


if __name__ == "__main__":
	main()
