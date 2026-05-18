#!/usr/bin/env python3
"""Query the agent-PR registry written by hooks/agent-registry-tracker.py.

Subcommands:
  pr <number>        Which job/session owns PR #<number>?
  job <id>           Which PRs is background job <id> juggling?
  session <id>       Which PRs does session <id> own?
  list               All active job→PR mappings (latest entry per PR).
  raw                Dump the full registry as-is.

`Active` means the corresponding `~/.claude/jobs/<job_id>/` directory still
exists. Inactive entries are kept in the registry as history.
"""

import argparse
import json
import os
import sys

REGISTRY_PATH = os.path.expanduser("~/.claude/agent-registry.jsonl")
JOBS_ROOT = os.path.expanduser("~/.claude/jobs")


def load_entries():
	if not os.path.exists(REGISTRY_PATH):
		return []
	entries = []
	with open(REGISTRY_PATH, "r", encoding="utf-8") as handle:
		for line in handle:
			line = line.strip()
			if not line:
				continue
			try:
				entries.append(json.loads(line))
			except ValueError:
				continue
	return entries


def latest_per_pr(entries):
	"""Return dict[pr_number] = latest entry (by ts)."""
	latest = {}
	for entry in entries:
		pr = entry.get("pr_number")
		if pr is None:
			continue
		current = latest.get(pr)
		if current is None or entry.get("ts", "") >= current.get("ts", ""):
			latest[pr] = entry
	return latest


def job_alive(job_id):
	if not job_id:
		return False
	return os.path.isdir(os.path.join(JOBS_ROOT, job_id))


def live_session_name(job_id):
	"""Fresh name from state.json; preferred over the cached value when present."""
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


def fmt_entry(entry, show_pr=True):
	pieces = []
	if show_pr:
		pieces.append(f"PR #{entry.get('pr_number')}")
	job_id = entry.get("job_id")
	if job_id:
		alive = "alive" if job_alive(job_id) else "gone"
		name = live_session_name(job_id) or entry.get("session_name")
		label = f"'{name}' " if name else ""
		pieces.append(f"job {label}{job_id} ({alive})")
	else:
		session = entry.get("session_id")
		if session:
			pieces.append(f"session {session[:8]} (interactive)")
	branch = entry.get("branch")
	if branch:
		pieces.append(f"branch {branch}")
	title = entry.get("title")
	if title:
		pieces.append(f'"{title}"')
	repo = entry.get("repo")
	if repo:
		pieces.append(repo)
	url = entry.get("pr_url")
	if url and not show_pr:
		pieces.append(url)
	ts = entry.get("ts")
	if ts:
		pieces.append(ts)
	return "  ".join(pieces)


def cmd_pr(args):
	entries = [e for e in load_entries() if e.get("pr_number") == args.number]
	if not entries:
		print(f"No registry entries for PR #{args.number}.")
		return 1
	entries.sort(key=lambda e: e.get("ts", ""))
	print(f"PR #{args.number} — {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:")
	for entry in entries:
		action = entry.get("action", "?")
		print(f"  [{action:6}] {fmt_entry(entry, show_pr=False)}")
	return 0


def cmd_job(args):
	prs = latest_per_pr(e for e in load_entries() if e.get("job_id") == args.id)
	if not prs:
		print(f"No registry entries for job {args.id}.")
		return 1
	alive = "alive" if job_alive(args.id) else "gone"
	print(f"Job {args.id} ({alive}) — {len(prs)} PR(s):")
	for pr in sorted(prs):
		print(f"  {fmt_entry(prs[pr])}")
	return 0


def cmd_session(args):
	prs = latest_per_pr(e for e in load_entries() if e.get("session_id") == args.id)
	if not prs:
		print(f"No registry entries for session {args.id}.")
		return 1
	print(f"Session {args.id} — {len(prs)} PR(s):")
	for pr in sorted(prs):
		print(f"  {fmt_entry(prs[pr])}")
	return 0


def cmd_list(args):
	prs = latest_per_pr(load_entries())
	if not prs:
		print("Registry is empty.")
		return 0
	rows = sorted(prs.values(), key=lambda e: e.get("ts", ""), reverse=True)
	if args.alive_only:
		rows = [e for e in rows if job_alive(e.get("job_id"))]
		if not rows:
			print("No PRs owned by live background jobs.")
			return 0
	print(f"{len(rows)} tracked PR(s) (latest entry per PR):")
	for entry in rows:
		print(f"  {fmt_entry(entry)}")
	return 0


def cmd_raw(args):
	if not os.path.exists(REGISTRY_PATH):
		print("Registry file does not exist yet.")
		return 0
	with open(REGISTRY_PATH, "r", encoding="utf-8") as handle:
		sys.stdout.write(handle.read())
	return 0


def main():
	parser = argparse.ArgumentParser(prog="agents", description=__doc__)
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_pr = sub.add_parser("pr", help="Show entries for a PR number.")
	p_pr.add_argument("number", type=int)
	p_pr.set_defaults(func=cmd_pr)

	p_job = sub.add_parser("job", help="Show PRs owned by a background job id.")
	p_job.add_argument("id")
	p_job.set_defaults(func=cmd_job)

	p_session = sub.add_parser("session", help="Show PRs owned by a session id.")
	p_session.add_argument("id")
	p_session.set_defaults(func=cmd_session)

	p_list = sub.add_parser("list", help="List the latest entry for every tracked PR.")
	p_list.add_argument("--alive-only", action="store_true", help="Only PRs whose job dir still exists.")
	p_list.set_defaults(func=cmd_list)

	p_raw = sub.add_parser("raw", help="Dump the registry file verbatim.")
	p_raw.set_defaults(func=cmd_raw)

	args = parser.parse_args()
	sys.exit(args.func(args))


if __name__ == "__main__":
	main()
