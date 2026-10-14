#!/usr/bin/env python3
"""PreToolUse hook: enforce <type>/<label> branch naming and worktree-only creation."""

import json
import os
import re
import shlex
import subprocess
import sys

KEBAB = r'[a-z0-9][a-z0-9-]*'
BRANCH_RE = re.compile(r'^(' + KEBAB + r')/(' + KEBAB + r')$')
SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')

# Longest branch name, and so longest worktree folder name (the folder is the
# branch with '/' as '-'). Forge on Windows is not long-path aware, and its
# deepest build file sits about 170 characters below the worktree root, so a
# root past ~90 characters breaks the build at MAX_PATH (260).
MAX_NAME_LENGTH = 40
WORKTREES_DIR = ".claude/worktrees/"

# Words dropped from the end of a shortened label: they carry no meaning there.
TRAILING_FILLER = {
	"a", "an", "and", "as", "at", "by", "for", "from", "in", "into",
	"of", "on", "or", "the", "to", "with",
}

# Registry of opt-in path-override mappings. A file at
# .claude/worktrees/.branches/<basename> whose contents equal a target branch
# tells the hook to permit `git worktree add .claude/worktrees/<basename> -b
# <target-branch>` even when <basename> != <branch>.replace('/', '-').
# The file lives outside the to-be-created worktree directory so it doesn't
# collide with `git worktree add`'s requirement of an empty target dir.
BRANCH_REGISTRY_DIR = ".claude/worktrees/.branches"

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

MSG_TOO_LONG = (
	"Branch name '{name}' is {length} characters; the limit is {limit}.\n"
	"Long names push Windows build paths past MAX_PATH. Shorten the label,\n"
	"e.g. {suggestion} (the label cut at a word, trailing filler dropped)."
)

MSG_FOLDER_TOO_LONG = (
	"Worktree folder '{name}' is {length} characters; the limit is {limit}.\n"
	"Long folders push Windows build paths past MAX_PATH. Use a shorter name."
)

MSG_MISMATCH = (
	"Worktree path and branch do not match.\n"
	"Branch {branch} must live at {expected}.\n"
	"To opt a shortened/combined path in, write the branch name into\n"
	"  .claude/worktrees/.branches/<basename>\n"
	"before running `git worktree add`."
)


def short_branch(branch):
	"""Return `branch` cut to MAX_NAME_LENGTH at a word boundary of its label.

	Keeps the type, keeps whole kebab words of the label while they fit, then
	drops trailing filler words. A first word too long to fit is cut hard.
	"""
	if len(branch) <= MAX_NAME_LENGTH:
		return branch
	branch_type, _, label = branch.partition("/")
	budget = MAX_NAME_LENGTH - len(branch_type) - 1
	kept = []
	for word in label.split("-"):
		if len("-".join(kept + [word])) > budget:
			break
		kept.append(word)
	while len(kept) > 1 and kept[-1] in TRAILING_FILLER:
		kept.pop()
	short_label = "-".join(kept) if kept else label[:budget].rstrip("-")
	return branch_type + "/" + short_label


def check_branch_name(branch):
	"""Block a branch name that is malformed or longer than MAX_NAME_LENGTH."""
	if not BRANCH_RE.match(branch):
		block(MSG_INVALID_BRANCH.format(name=branch))
	if len(branch) > MAX_NAME_LENGTH:
		block(MSG_TOO_LONG.format(
			name=branch, length=len(branch), limit=MAX_NAME_LENGTH,
			suggestion=short_branch(branch)))


def check_worktree_folder(path):
	"""Block a worktree folder under .claude/worktrees/ past MAX_NAME_LENGTH."""
	if path is None or WORKTREES_DIR not in path.replace("\\", "/") + "/":
		return
	name = os.path.basename(path.replace("\\", "/").rstrip("/"))
	if len(name) > MAX_NAME_LENGTH:
		block(MSG_FOLDER_TOO_LONG.format(
			name=name, length=len(name), limit=MAX_NAME_LENGTH))


def expected_path(branch):
	return ".claude/worktrees/" + branch.replace("/", "-")


def registered_branch_for_path(path):
	"""Return the branch this worktree path is opted in to, or None.

	Reads BRANCH_REGISTRY_DIR/<basename(path)> if present and returns its
	stripped contents. Any I/O error returns None — the hook then falls back
	to strict basename↔branch matching.
	"""
	if not path:
		return None
	basename = os.path.basename(path.rstrip("/"))
	if not basename:
		return None
	registry_file = os.path.join(BRANCH_REGISTRY_DIR, basename)
	try:
		with open(registry_file, "r", encoding="utf-8") as handle:
			return handle.read().strip()
	except OSError:
		return None


def path_matches_branch(path, branch):
	"""True when `path` is an acceptable worktree location for `branch`.

	Default rule: basename equals branch.replace('/', '-'). Opt-in: a registry
	file at .claude/worktrees/.branches/<basename> whose contents equal the
	branch name unblocks shortened or combined-branch paths.
	"""
	if path == expected_path(branch):
		return True
	registered = registered_branch_for_path(path)
	return registered is not None and registered == branch


def block(reason):
	print(json.dumps({"decision": "block", "reason": reason}))
	sys.exit(2)


def check_create(branch):
	"""Block every branch creation outside of `git worktree add -b`."""
	check_branch_name(branch)
	block(MSG_USE_WORKTREE)


def check_worktree_add(tokens):
	"""Validate `git worktree add` — cap the folder, and require a matching
	path and a short valid branch when -b is used."""
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
	if branch is not None:
		check_branch_name(branch)
	check_worktree_folder(path)
	if branch is None:
		return
	if path is None or not path_matches_branch(path, branch):
		block(MSG_MISMATCH.format(branch=branch, expected=expected_path(branch)))


def is_branch_fast_forward(branch, commit):
	"""True when `branch` already exists locally AND `commit` is a descendant of it.

	A descendant relationship means moving `branch` to `commit` is a true
	fast-forward (no commits on the current branch tip would be discarded).
	Both git invocations are read-only. Returns False on any subprocess
	failure so the caller falls back to the strict block path.
	"""
	try:
		exists = subprocess.run(
			["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + branch],
			capture_output=True, text=True, check=False,
		)
		if exists.returncode != 0:
			return False
		ff = subprocess.run(
			["git", "merge-base", "--is-ancestor", branch, commit],
			capture_output=True, text=True, check=False,
		)
		return ff.returncode == 0
	except (OSError, subprocess.SubprocessError):
		return False


def check_git_branch(tokens):
	"""`git branch` — only intervene when a new branch is being created."""
	for token in tokens:
		if token in NON_CREATE_BRANCH_FLAGS:
			return
	positional = [token for token in tokens if not token.startswith("-")]
	if not positional:
		return
	# `git branch -f <existing-branch> <commit>` is permitted when the move is
	# a true fast-forward (the new commit descends from the current branch
	# tip). Other -f invocations — creating a new branch, rewinding to a
	# non-ancestor — continue to flow through the create-branch block path.
	has_force = any(token in ("-f", "--force") for token in tokens)
	if has_force and len(positional) >= 1:
		branch = positional[0]
		commit = positional[1] if len(positional) >= 2 else "HEAD"
		if is_branch_fast_forward(branch, commit):
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
	if subcommand == "worktree" and rest and rest[0] == "move":
		positional = [token for token in rest[1:] if not token.startswith("-")]
		if len(positional) >= 2:
			check_worktree_folder(positional[1])
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
