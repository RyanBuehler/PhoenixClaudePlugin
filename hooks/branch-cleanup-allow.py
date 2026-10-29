#!/usr/bin/env python3
"""PreToolUse hook: allow an agent to delete its own `<type>/<label>` branches.

Allows `git branch -d|-D <branch>...` and `git push <remote> --delete <branch>...` (or
`:<branch>`) without a prompt, but only when every branch is named `<type>/<label>` with a
type the plugin creates, and every piece of the command is one of those deletions. Anything
else, such as `main`, a bare name, a glob, or a deletion chained with another command, falls
through to the normal permission flow.
"""

import json
import re
import shlex
import sys

TYPES = ("challenge", "bug", "doc", "ci", "misc")
BRANCH_RE = re.compile(r'^(' + '|'.join(TYPES) + r')/[a-z0-9][a-z0-9-]*$')
SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')
LOCAL_DELETE_FLAGS = {"-d", "-D", "--delete"}
PUSH_FORCE_FLAGS = {"--force", "-f", "--force-with-lease"}


def respond(reason):
	print(json.dumps({
		"hookSpecificOutput": {
			"hookEventName": "PreToolUse",
			"permissionDecision": "allow",
			"permissionDecisionReason": reason,
		}
	}))
	sys.exit(0)


def strip_git_options(tokens):
	"""Drop `-C <path>` and `-c <k=v>` between `git` and the subcommand."""
	rest = tokens[1:]
	while rest and rest[0] in ("-C", "-c") and len(rest) >= 2:
		rest = rest[2:]
	return rest


def only_branches(names):
	return bool(names) and all(BRANCH_RE.match(name) for name in names)


def deletes_own_branches(tokens):
	if not tokens or tokens[0] != "git":
		return False
	rest = strip_git_options(tokens)
	if not rest:
		return False
	if rest[0] == "branch":
		flags = [arg for arg in rest[1:] if arg.startswith("-")]
		names = [arg for arg in rest[1:] if not arg.startswith("-")]
		return (
			bool(flags)
			and all(flag in LOCAL_DELETE_FLAGS or flag == "-f" for flag in flags)
			and any(flag in LOCAL_DELETE_FLAGS for flag in flags)
			and only_branches(names)
		)
	if rest[0] == "push":
		flags = [arg for arg in rest[1:] if arg.startswith("-")]
		positional = [arg for arg in rest[1:] if not arg.startswith("-")]
		if len(positional) < 2 or any(flag in PUSH_FORCE_FLAGS for flag in flags):
			return False
		refs = positional[1:]
		if "--delete" in flags or "-d" in flags:
			return only_branches(refs)
		return all(ref.startswith(":") for ref in refs) and only_branches(
			[ref[1:] for ref in refs]
		)
	return False


def main():
	data = json.load(sys.stdin)
	command = data.get("tool_input", {}).get("command", "")
	pieces = [piece.strip() for piece in SEPARATOR.split(command) if piece.strip()]
	if not pieces:
		print("{}")
		sys.exit(0)
	for piece in pieces:
		try:
			tokens = shlex.split(piece)
		except ValueError:
			print("{}")
			sys.exit(0)
		tokens = [token for token in tokens if not REDIRECT_RE.match(token)]
		if not deletes_own_branches(tokens):
			print("{}")
			sys.exit(0)
	respond("Deleting a plugin-created <type>/<label> branch.")


if __name__ == "__main__":
	main()
