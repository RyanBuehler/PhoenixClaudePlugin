#!/usr/bin/env python3
"""Print the path of the newest Crucible CLI that Forge built in the main checkout.

Forge places the binary under a per-profile subtree whose name varies with host and build config
(`crucible-windows/bin/crucible.exe`, `crucible/bin/crucible`, ...), in both the configured build
tree and the bootstrap output. A stale copy still reports a plausible version, so the newest wins.
The main checkout is resolved from git, so a worktree finds the binary the main checkout built.

  crucible_path.py [--root <repo-root>]

Exit status: 0 with the path on stdout, 1 with the reason on stderr.
"""

import argparse
import subprocess
import sys
from pathlib import Path

BUILD_TREES = ("Applications/Forge/.forge", "Applications/Forge/.forge-out")
BINARY_NAMES = ("crucible", "crucible.exe")


def MainRoot():
	result = subprocess.run(
		["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
		capture_output=True, text=True, check=False)
	if result.returncode != 0:
		return Path.cwd()
	return Path(result.stdout.strip()).parent


def FindNewest(root):
	candidates = []
	for tree in BUILD_TREES:
		base = root / tree
		if not base.is_dir():
			continue
		for name in BINARY_NAMES:
			candidates.extend(
				path for path in base.rglob(name) if path.is_file() and path.parent.name == "bin")
	if not candidates:
		return None
	return max(candidates, key=lambda path: path.stat().st_mtime)


def Main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--root", type=Path, help="repository root (default: the main checkout)")
	arguments = parser.parse_args()
	root = arguments.root or MainRoot()
	found = FindNewest(root)
	if found is None:
		print(f"crucible not found under {root}; run /phoe:build crucible first", file=sys.stderr)
		return 1
	print(found.as_posix())
	return 0


if __name__ == "__main__":
	sys.exit(Main())
