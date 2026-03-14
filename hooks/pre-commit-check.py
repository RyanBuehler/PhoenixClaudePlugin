#!/usr/bin/env python3
"""PreToolUse hook: blocks git commit commands until formatting/linting is run."""

import sys
import json

def main():
	input_data = json.load(sys.stdin)
	command = input_data.get("tool_input", {}).get("command", "")

	if "git commit" in command:
		result = {
			"decision": "block",
			"reason": (
				"Run formatting and linting before committing:\n"
				"1. python Tools/format.py --files=staged\n"
				"2. python Tools/format.py --files=staged -error\n"
				"3. python Tools/tidy.py\n"
				"\n"
				"If all pass, proceed with the commit."
			),
		}
		print(json.dumps(result))
		sys.exit(2)

	print("{}")
	sys.exit(0)

if __name__ == "__main__":
	main()
