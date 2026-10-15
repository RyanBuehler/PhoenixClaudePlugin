#!/usr/bin/env python3
"""Append one run's workflow-friction entry to the main checkout's .claude/AGENT_FEEDBACK.md.

The log is long-lived and append-only, so the entry is added with a dated heading and the earlier
content is checked to be intact afterward. The main checkout is resolved from git, so the call
works from inside any worktree.

  append_feedback.py --run "/phoe:execute 3" [--log <path>] [--date YYYY-MM-DD] [<entry-file>]

The entry body is read from <entry-file>, or from stdin when it is omitted or `-`. A blank body
appends nothing. Exit status: 0 on success or nothing to append, 1 with the reason on stderr.
"""

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

LOG_RELATIVE = Path(".claude") / "AGENT_FEEDBACK.md"


def MainRoot():
	result = subprocess.run(
		["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
		capture_output=True, text=True, check=False)
	if result.returncode != 0:
		return None
	return Path(result.stdout.strip()).parent


def ReadBody(source):
	if source in (None, "-"):
		return sys.stdin.read()
	return Path(source).read_text(encoding="utf-8")


def Separator(existing):
	"""Return what keeps one blank line between the earlier content and the new heading."""
	if not existing:
		return ""
	tail = existing[-4:].replace(b"\r\n", b"\n")
	if tail.endswith(b"\n\n"):
		return ""
	if tail.endswith(b"\n"):
		return "\n"
	return "\n\n"


def Main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--run", required=True, help='the invocation, e.g. "/phoe:execute 3"')
	parser.add_argument("--log", type=Path, help="log path (default: the main checkout's log)")
	parser.add_argument("--date", help="entry date (default: today)")
	parser.add_argument("entry", nargs="?", help="file holding the entry body (default: stdin)")
	arguments = parser.parse_args()

	body = ReadBody(arguments.entry).strip("\n")
	if not body.strip():
		print("nothing to append")
		return 0

	log = arguments.log
	if log is None:
		root = MainRoot()
		if root is None:
			print("not inside a git checkout; pass --log", file=sys.stderr)
			return 1
		log = root / LOG_RELATIVE

	log.parent.mkdir(parents=True, exist_ok=True)
	existing = log.read_bytes() if log.exists() else b""
	date = arguments.date or datetime.date.today().isoformat()
	entry = f"{Separator(existing)}## {date} - {arguments.run}\n\n{body}\n".encode("utf-8")

	with log.open("ab") as handle:
		handle.write(entry)

	after = log.read_bytes()
	if after != existing + entry:
		print(f"{log} changed during the append; check it by hand", file=sys.stderr)
		return 1
	print(f"appended {len(entry)} bytes to {log.as_posix()}")
	return 0


if __name__ == "__main__":
	sys.exit(Main())
