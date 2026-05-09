#!/usr/bin/env python3
"""PreToolUse hook: enforce <type>/<label> branch naming and worktree-only creation."""

import json
import re
import shlex
import sys

KEBAB = r'[a-z0-9][a-z0-9-]*'
BRANCH_RE = re.compile(r'^(' + KEBAB + r')/(' + KEBAB + r')$')
SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')

NON_CREATE_BRANCH_FLAGS = {
	"-d", "-D", "--delete",
	"-m", "-M", "--move",
	"-c", "-C", "--copy",
	"-l", "--list",
	"-a", "--all",
	"-r", "--remotes",
	"-v", "-vv", "--verbose",
	"-q", "--quiet",
	"--column", "--no-column",
	"--show-current", "--edit-description",
	"--set-upstream-to", "--unset-upstream",
	"--contains", "--no-contains",
	"--merged", "--no-merged",
	"--points-at",
}

MSG_USE_WORKTREE = (
	"Create branches via worktree only. Run:\n"
	"  git worktree add .claude/worktrees/<type>-<label> -b <type>/<label>\n"
	"from the main repo root."
)

MSG_INVALID_BRANCH = (
	"Branch name '{name}' is invalid.\n"
	"Required: <type>/<label> where both are lowercase kebab-case\n"
	"(^[a-z0-9][a-z0-9-]*$). Examples: challenge/crucible-update-ui,\n"
	"bug/windows-liaison-fix-focus, doc/branch-workflow, ci/pin-clang-19."
)

MSG_MISMATCH = (
	"Worktree path and branch do not match.\n"
	"Branch {branch} must live at {expected}."
)


def expected_path(branch):
	return ".claude/worktrees/" + branch.replace("/", "-")


def block(reason):
	print(json.dumps({"decision": "block", "reason": reason}))
	sys.exit(2)


def check_create(branch):
	"""Block every branch creation outside of `git worktree add -b`."""
	if not BRANCH_RE.match(branch):
		block(MSG_INVALID_BRANCH.format(name=branch))
	block(MSG_USE_WORKTREE)


def check_worktree_add(tokens):
	"""Validate `git worktree add` — require matching path when -b is used."""
	path = None
	branch = None
	index = 0
	while index < len(tokens):
		token = tokens[index]
		if token == "-b" or token == "-B":
			if index + 1 >= len(tokens):
				return
			branch = tokens[index + 1]
			index += 2
			continue
		if token.startswith("-"):
			index += 1
			continue
		if path is None:
			path = token
		index += 1
	if branch is None:
		return
	if not BRANCH_RE.match(branch):
		block(MSG_INVALID_BRANCH.format(name=branch))
	if path is None or path != expected_path(branch):
		block(MSG_MISMATCH.format(branch=branch, expected=expected_path(branch)))


def check_git_branch(tokens):
	"""`git branch` — only intervene when a new branch is being created."""
	for token in tokens:
		if token in NON_CREATE_BRANCH_FLAGS:
			return
	positional = [token for token in tokens if not token.startswith("-")]
	if not positional:
		return
	check_create(positional[0])


def inspect_git(tokens):
	if not tokens:
		return
	subcommand = tokens[0]
	rest = tokens[1:]
	if subcommand == "checkout":
		for index, token in enumerate(rest):
			if token in ("-b", "-B") and index + 1 < len(rest):
				check_create(rest[index + 1])
				return
		return
	if subcommand == "switch":
		for index, token in enumerate(rest):
			if token in ("-c", "-C") and index + 1 < len(rest):
				check_create(rest[index + 1])
				return
		return
	if subcommand == "branch":
		check_git_branch(rest)
		return
	if subcommand == "worktree" and rest and rest[0] == "add":
		check_worktree_add(rest[1:])
		return


def main():
	data = json.load(sys.stdin)
	command = data.get("tool_input", {}).get("command", "")
	for piece in SEPARATOR.split(command):
		piece = piece.strip()
		if not piece:
			continue
		try:
			tokens = shlex.split(piece)
		except ValueError:
			continue
		tokens = [token for token in tokens if not REDIRECT_RE.match(token)]
		if not tokens or tokens[0] != "git":
			continue
		inspect_git(tokens[1:])
	print("{}")
	sys.exit(0)


if __name__ == "__main__":
	main()
