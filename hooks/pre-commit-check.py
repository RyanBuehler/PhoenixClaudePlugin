#!/usr/bin/env python3
"""PreToolUse hook: reminds the agent to run verification before committing."""

import sys
import json

REMINDER = (
	"REMINDER: Have you run the full verification sequence?\n"
	"  1. cmake --build build --config Release --parallel\n"
	"  2. python Tools/format.py --files=staged\n"
	"  3. python Tools/format.py --files=staged -error\n"
	"  4. python Tools/tidy.py\n"
	"  5. ctest --test-dir build -C Release --output-on-failure\n"
	"\n"
	"If not, consider running /phoe:verify before committing."
)

def main():
	input_data = json.load(sys.stdin)
	command = input_data.get("tool_input", {}).get("command", "")

	if "git commit" in command:
		print(REMINDER, file=sys.stderr)

	print("{}")
	sys.exit(0)

if __name__ == "__main__":
	main()
