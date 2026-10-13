#!/usr/bin/env python3
"""PreToolUse hook: deny Bash forms the operating guide prohibits.

Covers four rules that are mechanical to check: `cd` combined with `git`,
manufactured machine load, recursive grep/find sweeps of a worktree root, and
the `git grep` forms that read as a false miss.
"""

import glob
import json
import os
import re
import shlex
import sys

SEPARATOR = re.compile(r'(&&|\|\||\||;|\n)')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')
ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')

FORK_BOMB = re.compile(r':\s*\(\)\s*\{')
SPINNER = re.compile(r'\bwhile\s+(?::|true|\[\s*1\s*\])\s*;\s*do\s*(?::|true)?\s*;?\s*done\b')
LOAD_COMMANDS = {"stress", "stress-ng"}
FILL_SOURCES = ("/dev/zero", "/dev/urandom", "/dev/random")
PARALLEL_COMMANDS = {"make", "ninja", "forge", "ctest", "cmake"}
PARALLEL_FLAG = re.compile(r'^-j(\d+)$')
PARALLEL_LONG = re.compile(r'^--parallel=(\d+)$')

SWEPT_NAMES = (".forge", ".bootstrap-out", "worktrees")
RECURSIVE_CLUSTER = re.compile(r'^-[A-Za-z]*[rR][A-Za-z]*$')
CONTEXT_FLAG = re.compile(r'^-([ABC]\d*|\d+)$')

MSG_CD_GIT = (
	"Do not combine `cd` and `git` in one command: changing into an untrusted directory\n"
	"before git exposes you to bare-repository attacks. Use `git -C <path> <args>`."
)
MSG_LOAD = (
	"Manufacturing machine load needs explicit, per-instance permission from the user.\n"
	"Blocked: {what}. The host is shared with the user and with other sessions."
)
MSG_SWEEP = (
	"`{tool}` from this directory also sweeps .forge*/, .bootstrap-out/ and .claude/worktrees/,\n"
	"so deleted symbols still appear. Use `git grep` (tracked files in this worktree only),\n"
	"or exclude all three."
)
MSG_GIT_GREP_CONTEXT = (
	"`git grep` parses a context flag after the pattern as a revision. Put `{flag}` before the pattern."
)
MSG_GIT_GREP_INCLUDE = (
	"`git grep` has no --include. Give a pathspec instead, e.g. `git grep PATTERN -- '*.cppm'`."
)
MSG_GIT_GREP_CHAIN = (
	"`git grep A && git grep B` never runs B after a miss, which reads as a false absence.\n"
	"Chain with `;`."
)


def deny(reason):
	print(json.dumps({
		"hookSpecificOutput": {
			"hookEventName": "PreToolUse",
			"permissionDecision": "deny",
			"permissionDecisionReason": reason,
		}
	}))
	sys.exit(0)


def split_pieces(command):
	"""Yield (separator-before, tokens) for each simple command in `command`."""
	parts = SEPARATOR.split(command)
	separator = ""
	pieces = []
	for part in parts:
		if SEPARATOR.fullmatch(part):
			separator = part
			continue
		piece = part.strip().lstrip("({").strip()
		if not piece:
			continue
		try:
			tokens = shlex.split(piece)
		except ValueError:
			separator = ""
			continue
		tokens = [token for token in tokens if not REDIRECT_RE.match(token)]
		while tokens and ENV_ASSIGNMENT.match(tokens[0]):
			tokens = tokens[1:]
		if tokens:
			pieces.append((separator, tokens))
		separator = ""
	return pieces


def check_cd_git(pieces):
	heads = {tokens[0] for _, tokens in pieces}
	if "git" in heads and heads & {"cd", "pushd"}:
		deny(MSG_CD_GIT)


def check_load(command, pieces):
	if FORK_BOMB.search(command):
		deny(MSG_LOAD.format(what="fork bomb"))
	if SPINNER.search(command):
		deny(MSG_LOAD.format(what="busy-wait spinner"))
	cpus = os.cpu_count() or 1
	for _, tokens in pieces:
		head = tokens[0]
		if head in LOAD_COMMANDS:
			deny(MSG_LOAD.format(what=head))
		if head == "yes" and "/dev/null" in command:
			deny(MSG_LOAD.format(what="`yes` into /dev/null"))
		if head == "dd":
			sources = [t for t in tokens if t.startswith("if=") and t[3:] in FILL_SOURCES]
			sinks = [t for t in tokens if t.startswith("of=") and t[3:] != "/dev/null"]
			if sources and sinks:
				deny(MSG_LOAD.format(what="dd from " + sources[0][3:] + " to " + sinks[0][3:]))
		if head in PARALLEL_COMMANDS:
			jobs = parallel_jobs(tokens)
			if jobs is not None and jobs > cpus:
				deny(MSG_LOAD.format(what="%s parallelism %d exceeds the host's %d CPUs" % (head, jobs, cpus)))


def parallel_jobs(tokens):
	for index, token in enumerate(tokens):
		match = PARALLEL_FLAG.match(token) or PARALLEL_LONG.match(token)
		if match:
			return int(match.group(1))
		if token in ("-j", "--parallel") and index + 1 < len(tokens) and tokens[index + 1].isdigit():
			return int(tokens[index + 1])
	return None


def sweep_dirs_exist(cwd):
	return (
		os.path.isdir(os.path.join(cwd, ".bootstrap-out"))
		or os.path.isdir(os.path.join(cwd, ".claude", "worktrees"))
		or bool(glob.glob(os.path.join(cwd, ".forge*")))
	)


def excludes_all(text):
	return all(name in text for name in SWEPT_NAMES)


def is_root_target(path, cwd):
	if path in (".", "./"):
		return True
	return os.path.realpath(path) == os.path.realpath(cwd)


def check_sweep(pieces, cwd):
	if not sweep_dirs_exist(cwd):
		return
	for _, tokens in pieces:
		head = tokens[0]
		rest = tokens[1:]
		if head in ("grep", "egrep", "fgrep"):
			recursive = any(RECURSIVE_CLUSTER.match(t) for t in rest if not t.startswith("--")) \
				or "--recursive" in rest or "--dereference-recursive" in rest
			if not recursive:
				continue
			positional = [t for t in rest if not t.startswith("-")]
			has_pattern_flag = "-e" in rest or "-f" in rest
			paths = positional if has_pattern_flag else positional[1:]
			if paths and not any(is_root_target(p, cwd) for p in paths):
				continue
			if excludes_all(" ".join(t for t in rest if "exclude-dir" in t)):
				continue
			deny(MSG_SWEEP.format(tool="grep -r"))
		if head == "find":
			paths = []
			for token in rest:
				if token.startswith("-") or token in ("(", "!"):
					break
				paths.append(token)
			if paths and not any(is_root_target(p, cwd) for p in paths):
				continue
			if excludes_all(" ".join(rest)):
				continue
			deny(MSG_SWEEP.format(tool="find"))


def check_git_grep(pieces):
	previous_was_grep = False
	for separator, tokens in pieces:
		is_grep = tokens[0] == "git" and len(tokens) > 1 and tokens[1] == "grep"
		if is_grep and previous_was_grep and separator == "&&":
			deny(MSG_GIT_GREP_CHAIN)
		previous_was_grep = is_grep
		if not is_grep:
			continue
		args = tokens[2:]
		for token in args:
			if token == "--include" or token.startswith("--include="):
				deny(MSG_GIT_GREP_INCLUDE)
		seen_pattern = False
		skip_next = False
		for token in args:
			if token == "--":
				break
			if skip_next:
				skip_next = False
				seen_pattern = True
				continue
			if token in ("-e", "-f"):
				skip_next = True
				continue
			if CONTEXT_FLAG.match(token):
				if seen_pattern:
					deny(MSG_GIT_GREP_CONTEXT.format(flag=token))
				continue
			if token.startswith("-"):
				continue
			seen_pattern = True


def main():
	data = json.load(sys.stdin)
	command = data.get("tool_input", {}).get("command", "")
	cwd = data.get("cwd") or os.getcwd()
	pieces = split_pieces(command)
	check_cd_git(pieces)
	check_load(command, pieces)
	check_sweep(pieces, cwd)
	check_git_grep(pieces)
	print("{}")
	sys.exit(0)


if __name__ == "__main__":
	main()
