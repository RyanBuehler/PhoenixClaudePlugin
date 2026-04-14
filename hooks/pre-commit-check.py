#!/usr/bin/env python3
"""PreToolUse hook: blocks git push unless /phoe:verify has passed recently.

Only applies to pushes from the Phoenix engine repo. Pushes from other repos
(plugin repo, dotfiles, etc.) pass through without requiring verification,
since the verify sequence is C++/CMake specific.
"""

import json
import os
import re
import subprocess
import sys
import time

HOOK_DIR = os.path.join(os.path.expanduser("~"), ".claude", "tmp")
MARKER = os.path.join(HOOK_DIR, "verification-passed")
BYPASS = os.path.join(HOOK_DIR, "verification-bypass")
MAX_AGE_SECONDS = 1800  # 30 minutes

PHOENIX_REPO_MARKER = os.path.join("Applications", "Forge", "ForgeManifest.json")

REMINDER = (
	"Run /phoe:verify before pushing. It runs the full verification sequence:\n"
	"  1. Build (cmake)\n"
	"  2. Format (clang-format)\n"
	"  3. Lint (clang-tidy)\n"
	"  4. Test (ctest)\n"
	"\n"
	"Once all pass, /phoe:verify writes a marker file that allows the push.\n"
	"\n"
	"If this is NOT a Phoenix C++ push (e.g., docs, config, or a different repo),\n"
	"ask the user if verification can be skipped. If they confirm, run:\n"
	"  mkdir -p ~/.claude/tmp && touch ~/.claude/tmp/verification-bypass\n"
	"Then retry the push."
)

def effective_cwd(command: str) -> str:
	"""Extract the cwd the push will run under, honouring a leading `cd <path> &&`."""
	match = re.match(r"\s*cd\s+(\S+)\s*(?:&&|;)", command)
	if match:
		return os.path.expanduser(match.group(1))
	return os.getcwd()

def is_phoenix_engine_repo(path: str) -> bool:
	"""Return True only when `path` is inside the Phoenix engine repo."""
	try:
		result = subprocess.run(
			["git", "-C", path, "rev-parse", "--show-toplevel"],
			capture_output=True,
			text=True,
			check=True,
			timeout=5,
		)
	except (subprocess.SubprocessError, FileNotFoundError, OSError):
		return False
	repo_root = result.stdout.strip()
	return bool(repo_root) and os.path.isfile(os.path.join(repo_root, PHOENIX_REPO_MARKER))

def main():
	input_data = json.load(sys.stdin)
	command = input_data.get("tool_input", {}).get("command", "")

	if "git push" not in command:
		print("{}")
		sys.exit(0)

	if not is_phoenix_engine_repo(effective_cwd(command)):
		print("{}")
		sys.exit(0)

	# Check for bypass marker (non-C++ commits, user-approved)
	if os.path.isfile(BYPASS):
		try:
			os.remove(BYPASS)
			print("{}")
			sys.exit(0)
		except OSError:
			pass

	# Check for verification marker
	if os.path.isfile(MARKER):
		try:
			age = time.time() - os.path.getmtime(MARKER)
			if age <= MAX_AGE_SECONDS:
				os.remove(MARKER)
				print("{}")
				sys.exit(0)
		except OSError:
			pass

	# No valid marker — block with reminder
	result = {
		"decision": "block",
		"reason": REMINDER,
	}
	print(json.dumps(result))
	sys.exit(2)

if __name__ == "__main__":
	main()
