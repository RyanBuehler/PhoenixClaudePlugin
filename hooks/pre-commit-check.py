#!/usr/bin/env python3
"""PreToolUse hook: blocks git commit commands until formatting, linting, and tests are run."""

import sys
import json

def main():
	input_data = json.load(sys.stdin)
	command = input_data.get("tool_input", {}).get("command", "")

	if "git commit" in command:
		result = {
			"decision": "block",
			"reason": (
				"Run the full verification sequence before committing:\n"
				"1. cmake --build build --config Release --parallel\n"
				"2. python Tools/format.py --files=staged\n"
				"3. python Tools/format.py --files=staged -error\n"
				"4. python Tools/tidy.py\n"
				"5. ctest --test-dir build -C Release --output-on-failure\n"
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
