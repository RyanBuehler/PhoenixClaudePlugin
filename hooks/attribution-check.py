#!/usr/bin/env python3
"""PreToolUse hook: refuse Claude attribution in git/gh commands that publish.

The harness attribution settings are already off, so any trailer or banner is typed
by habit, and a squash merge copies a branch commit's trailers into main. Only the
attribution forms are refused. A bare mention of an assistant, or a path such as
`.claude/worktrees`, never trips the hook, and the working directory is never read.
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

# Only commands that write text somewhere durable are checked, so a read-only
# `git log | grep "Co-Authored-By: Claude"` audit still runs.
PUBLISHING_RE = re.compile(
	r"\bgit\s+(?:-C\s+\S+\s+)?(commit|tag|notes|merge)\b"
	r"|\bgh\s+(pr|issue|release)\s+(?!(list|view|diff|checks|status)\b)"
	r"|\bgh\s+api\b"
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
	print("{}")
	sys.exit(0)


if __name__ == "__main__":
	main()
