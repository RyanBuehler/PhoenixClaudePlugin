#!/usr/bin/env python3
"""PostToolUse hook: record which session/job owns which PR.

Watches `gh pr create` and `gh pr edit` invocations and appends a JSONL entry
to ~/.claude/agent-registry.jsonl so the `agents` skill can answer:

  - Which job owns PR #1234?
  - Which PRs is job 9271caec juggling?

Failures are silent — this hook is informational and must never block work.
"""

import datetime
import json
import os
import re
import shlex
import subprocess
import sys

REGISTRY_PATH = os.path.expanduser("~/.claude/agent-registry.jsonl")
JOBS_ROOT = os.path.expanduser("~/.claude/jobs")
SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')
PR_URL_RE = re.compile(r'https?://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)')


def find_gh_pr_invocations(command):
	"""Yield (action, tokens) for each `gh pr {create,edit}` piece of a command."""
	for piece in SEPARATOR.split(command):
		piece = piece.strip()
		if not piece:
			continue
		try:
			tokens = shlex.split(piece)
		except ValueError:
			continue
		tokens = [tok for tok in tokens if not REDIRECT_RE.match(tok)]
		if len(tokens) < 3:
			continue
		if tokens[0] != "gh" or tokens[1] != "pr":
			continue
		if tokens[2] in ("create", "edit"):
			yield tokens[2], tokens[3:]


def parse_flag_value(tokens, *names):
	"""Return the value of --flag=value or --flag value, or None."""
	for index, tok in enumerate(tokens):
		for name in names:
			if tok == name and index + 1 < len(tokens):
				return tokens[index + 1]
			prefix = name + "="
			if tok.startswith(prefix):
				return tok[len(prefix):]
	return None


def first_positional(tokens):
	"""Return the first non-flag token, skipping flag values."""
	skip_next = False
	for tok in tokens:
		if skip_next:
			skip_next = False
			continue
		if tok.startswith("-"):
			if "=" not in tok:
				skip_next = True
			continue
		return tok
	return None


def current_branch(cwd):
	try:
		result = subprocess.run(
			["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
			capture_output=True, text=True, check=False, timeout=5,
		)
		if result.returncode == 0:
			return result.stdout.strip()
	except (OSError, subprocess.SubprocessError):
		pass
	return None


def repo_slug(cwd):
	"""Best-effort owner/repo via `gh repo view`; cheap and offline if cached."""
	try:
		result = subprocess.run(
			["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
			cwd=cwd, capture_output=True, text=True, check=False, timeout=5,
		)
		if result.returncode == 0:
			return result.stdout.strip() or None
	except (OSError, subprocess.SubprocessError):
		pass
	return None


def job_id_from_env():
	"""Background-job id from CLAUDE_JOB_DIR (.../jobs/<id>); None for interactive."""
	job_dir = os.environ.get("CLAUDE_JOB_DIR")
	if not job_dir:
		return None
	return os.path.basename(job_dir.rstrip("/")) or None


def session_name_for_job(job_id):
	"""Read the friendly session name from ~/.claude/jobs/<id>/state.json."""
	if not job_id:
		return None
	state_path = os.path.join(JOBS_ROOT, job_id, "state.json")
	try:
		with open(state_path, "r", encoding="utf-8") as handle:
			state = json.load(handle)
	except (OSError, ValueError):
		return None
	name = state.get("name")
	return name if isinstance(name, str) and name else None


def tool_response_text(response):
	"""Flatten tool_response to a searchable string."""
	if isinstance(response, str):
		return response
	if isinstance(response, dict):
		parts = []
		for key in ("stdout", "output", "interrupted_output", "stderr"):
			value = response.get(key)
			if isinstance(value, str):
				parts.append(value)
		return "\n".join(parts)
	return ""


def extract_pr(action, tokens, response_text):
	"""Resolve (pr_number, pr_url) from output (create) or args (edit)."""
	match = PR_URL_RE.search(response_text)
	if match:
		return int(match.group(1)), match.group(0)
	if action == "edit":
		positional = first_positional(tokens)
		if positional and positional.isdigit():
			return int(positional), None
		if positional:
			pr_match = re.search(r'/pull/(\d+)', positional)
			if pr_match:
				return int(pr_match.group(1)), positional
	return None, None


def append_entry(entry):
	try:
		os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
		with open(REGISTRY_PATH, "a", encoding="utf-8") as handle:
			handle.write(json.dumps(entry) + "\n")
	except OSError:
		pass


def main():
	try:
		data = json.load(sys.stdin)
	except (ValueError, OSError):
		print("{}")
		sys.exit(0)
	command = data.get("tool_input", {}).get("command", "")
	if not command:
		print("{}")
		sys.exit(0)
	response_text = tool_response_text(data.get("tool_response"))
	cwd = data.get("cwd") or os.getcwd()
	session_id = data.get("session_id")
	job_id = job_id_from_env()
	for action, tokens in find_gh_pr_invocations(command):
		pr_number, pr_url = extract_pr(action, tokens, response_text)
		if pr_number is None:
			continue
		entry = {
			"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
			"action": action,
			"pr_number": pr_number,
			"session_id": session_id,
			"job_id": job_id,
			"session_name": session_name_for_job(job_id),
			"cwd": cwd,
			"branch": current_branch(cwd),
			"repo": repo_slug(cwd),
		}
		if pr_url:
			entry["pr_url"] = pr_url
		title = parse_flag_value(tokens, "--title", "-t")
		if title:
			entry["title"] = title
		append_entry(entry)
	print("{}")
	sys.exit(0)


if __name__ == "__main__":
	main()
