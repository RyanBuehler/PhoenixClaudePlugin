#!/usr/bin/env python3
"""PreToolUse hook: gate `git push` and `gh pr create`.

Verifies git identity and remote authentication first, and denies with the
failure when either is missing. When both hold, allows the command without a prompt.
"""

import json
import re
import shlex
import subprocess
import sys

SEPARATOR = re.compile(r'&&|\|\|?|;|\n')
REDIRECT_RE = re.compile(r'^[0-9]*[<>]+&?[0-9-]*$|^&>+$')
LS_REMOTE_TIMEOUT = 20

MSG_ALLOW = "{what}: git identity and authentication against '{remote}' check out."
MSG_NO_IDENTITY = "git {key} is not configured. Set it before pushing; the push was not attempted."
MSG_NO_AUTH = (
	"Authentication against '{remote}' failed, so the push was not attempted:\n{detail}"
)


def respond(decision, reason):
	print(json.dumps({
		"hookSpecificOutput": {
			"hookEventName": "PreToolUse",
			"permissionDecision": decision,
			"permissionDecisionReason": reason,
		}
	}))
	sys.exit(0)


def classify(tokens):
	"""Return (what, remote) for a gated command, else None."""
	if len(tokens) >= 2 and tokens[0] == "git" and tokens[1] == "push":
		args = tokens[2:]
		if any(arg in ("-n", "--dry-run") for arg in args):
			return None
		positional = [arg for arg in args if not arg.startswith("-")]
		return "git push", positional[0] if positional else "origin"
	if len(tokens) >= 3 and tokens[0] == "gh" and tokens[1] == "pr" and tokens[2] == "create":
		return "gh pr create", "origin"
	return None


def git_config(key):
	try:
		result = subprocess.run(
			["git", "config", key], capture_output=True, text=True, check=False,
		)
	except (OSError, subprocess.SubprocessError):
		return ""
	return result.stdout.strip()


def authenticates(remote):
	"""Return (ok, detail) for `git ls-remote <remote> HEAD`."""
	try:
		result = subprocess.run(
			["git", "ls-remote", remote, "HEAD"],
			capture_output=True, text=True, check=False, timeout=LS_REMOTE_TIMEOUT,
		)
	except subprocess.TimeoutExpired:
		return False, "timed out after %ds" % LS_REMOTE_TIMEOUT
	except (OSError, subprocess.SubprocessError) as error:
		return False, str(error)
	if result.returncode != 0:
		return False, result.stderr.strip()
	return True, ""


def main():
	data = json.load(sys.stdin)
	command = data.get("tool_input", {}).get("command", "")
	gated = None
	for piece in SEPARATOR.split(command):
		try:
			tokens = shlex.split(piece.strip())
		except ValueError:
			continue
		tokens = [token for token in tokens if not REDIRECT_RE.match(token)]
		gated = classify(tokens)
		if gated:
			break
	if not gated:
		print("{}")
		sys.exit(0)
	what, remote = gated
	for key in ("user.name", "user.email"):
		if not git_config(key):
			respond("deny", MSG_NO_IDENTITY.format(key=key))
	ok, detail = authenticates(remote)
	if not ok:
		respond("deny", MSG_NO_AUTH.format(remote=remote, detail=detail))
	respond("allow", MSG_ALLOW.format(what=what, remote=remote))


if __name__ == "__main__":
	main()
