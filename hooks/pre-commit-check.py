#!/usr/bin/env python3
"""PreToolUse hook: blocks git commit unless /phoe:verify has passed recently."""

import sys
import json
import os
import time

HOOK_DIR = os.path.join(os.path.expanduser("~"), ".claude", "tmp")
MARKER = os.path.join(HOOK_DIR, "verification-passed")
BYPASS = os.path.join(HOOK_DIR, "verification-bypass")
MAX_AGE_SECONDS = 1800  # 30 minutes

REMINDER = (
	"Run /phoe:verify before committing. It runs the full verification sequence:\n"
	"  1. Build (cmake)\n"
	"  2. Format (clang-format)\n"
	"  3. Lint (clang-tidy)\n"
	"  4. Test (ctest)\n"
	"\n"
	"Once all pass, /phoe:verify writes a marker file that allows the commit.\n"
	"\n"
	"If this is NOT a Phoenix C++ commit (e.g., docs, config, or a different repo),\n"
	"ask the user if verification can be skipped. If they confirm, run:\n"
	"  mkdir -p ~/.claude/tmp && touch ~/.claude/tmp/verification-bypass\n"
	"Then retry the commit."
)

def main():
	input_data = json.load(sys.stdin)
	command = input_data.get("tool_input", {}).get("command", "")

	if "git commit" not in command:
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
				# Verification passed recently — allow and clean up
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
