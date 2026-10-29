#!/usr/bin/env python3
"""PreToolUse hook: allow an agent to delete its own `<type>/<label>` branches.

Allows `git branch -d|-D <branch>...` and `git push <remote> --delete <branch>...` (or
`:<branch>`) without a prompt, but only when every branch is named `<type>/<label>` with a
type the plugin creates, and every piece of the command is one of those deletions. It also
refuses to lose work: a local deletion needs the branch's tip to be on a remote branch, and a
remote deletion needs the branch to have no open pull request. Anything else, such as `main`, a
bare name, a glob, a failed check, or a deletion chained with another command, falls through to
the normal permission flow.
"""

import json
import re
import shlex
import subprocess
import sys

TYPES = ("challenge", "bug", "doc", "ci", "misc")
BRANCH_RE = re.compile(r'^(' + '|'.join(TYPES) + r')/[a-z0-9][a-z0-9-]*$')
SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')
LOCAL_DELETE_FLAGS = {"-d", "-D", "--delete"}
PUSH_FORCE_FLAGS = {"--force", "-f", "--force-with-lease"}
CHECK_TIMEOUT = 20


def respond(reason):
	print(json.dumps({
		"hookSpecificOutput": {
			"hookEventName": "PreToolUse",
			"permissionDecision": "allow",
			"permissionDecisionReason": reason,
		}
	}))
	sys.exit(0)


def split_git_options(tokens):
	"""Return (`-C <path>` directory or None, tokens after the git options)."""
	rest = tokens[1:]
	directory = None
	while rest and rest[0] in ("-C", "-c") and len(rest) >= 2:
		if rest[0] == "-C":
			directory = rest[1]
		rest = rest[2:]
	return directory, rest


def only_branches(names):
	return bool(names) and all(BRANCH_RE.match(name) for name in names)


def parse_deletion(tokens):
	"""Return (kind, directory, branches) for a deletion of own-pattern branches, else None."""
	if not tokens or tokens[0] != "git":
		return None
	directory, rest = split_git_options(tokens)
	if not rest:
		return None
	if rest[0] == "branch":
		flags = [arg for arg in rest[1:] if arg.startswith("-")]
		names = [arg for arg in rest[1:] if not arg.startswith("-")]
		if (
			flags
			and all(flag in LOCAL_DELETE_FLAGS or flag == "-f" for flag in flags)
			and any(flag in LOCAL_DELETE_FLAGS for flag in flags)
			and only_branches(names)
		):
			return "local", directory, names
		return None
	if rest[0] == "push":
		flags = [arg for arg in rest[1:] if arg.startswith("-")]
		positional = [arg for arg in rest[1:] if not arg.startswith("-")]
		if len(positional) < 2 or any(flag in PUSH_FORCE_FLAGS for flag in flags):
			return None
		refs = positional[1:]
		if "--delete" in flags or "-d" in flags:
			names = refs
		elif all(ref.startswith(":") for ref in refs):
			names = [ref[1:] for ref in refs]
		else:
			return None
		return ("remote", directory, names) if only_branches(names) else None
	return None


def run(argv, directory):
	try:
		return subprocess.run(
			argv, capture_output=True, text=True, check=False,
			cwd=directory, timeout=CHECK_TIMEOUT,
		)
	except (OSError, subprocess.SubprocessError):
		return None


def tip_is_on_a_remote(branch, directory):
	"""A missing local branch loses nothing; otherwise its tip must be on a remote branch."""
	tip = run(["git", "rev-parse", "--verify", "-q", "refs/heads/" + branch], directory)
	if tip is None:
		return False
	if tip.returncode != 0:
		return True
	remotes = run(["git", "branch", "-r", "--contains", tip.stdout.strip()], directory)
	return remotes is not None and remotes.returncode == 0 and bool(remotes.stdout.strip())


def has_no_open_pull_request(branch, directory):
	result = run(
		["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number",
		"--jq", "length"],
		directory,
	)
	return result is not None and result.returncode == 0 and result.stdout.strip() == "0"


def is_safe(deletion):
	kind, directory, branches = deletion
	check = tip_is_on_a_remote if kind == "local" else has_no_open_pull_request
	return all(check(branch, directory) for branch in branches)


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
		deletion = parse_deletion(tokens)
		if not deletion or not is_safe(deletion):
			print("{}")
			sys.exit(0)
	respond("Deleting <type>/<label> branches that lose no work.")


if __name__ == "__main__":
	main()
