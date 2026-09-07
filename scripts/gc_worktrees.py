#!/usr/bin/env python3
"""Collect worktrees whose branch has landed on origin/main.

Dry-run by default: it prints a verdict per worktree and removes nothing.
Pass --apply to act. Every worktree is either a CANDIDATE (removable) or is
KEPT with a stated reason; nothing is skipped silently.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The remote-tracking ref a branch must have reached to count as landed.
DEFAULT_UPSTREAM = "origin/main"

# `git worktree list --porcelain` emits "<key> <value>" or a bare flag per line,
# with a blank line between entries.
PORCELAIN_FLAGS = {"bare", "detached", "locked", "prunable"}

# How many merged pull requests to pull in the single bulk query. Branches older
# than this window fall back to a per-branch lookup, so the number is a cost
# knob, not a correctness one.
MERGED_PR_WINDOW = 1000

# Reasons a worktree is removable. Ordered by strength of evidence.
LANDED_ANCESTOR = "landed: merged into {upstream}"
LANDED_PR = "landed: PR #{number} merged"
LANDED_GONE = "landed: upstream gone (unverified)"

# Reasons a worktree is kept. A worktree is kept on the first that applies.
KEEP_MAIN = "main checkout"
KEEP_LOCKED = "locked"
KEEP_IN_USE = "in use by pid {pid}"
KEEP_BUILD_LOCK = "build lock held ({lock})"
KEEP_DIRTY = "{count} uncommitted change(s)"
KEEP_DETACHED = "detached HEAD"
KEEP_UNPUSHED = "{count} commit(s) not on {upstream}"
KEEP_GONE_UNMERGED = "upstream gone but no merged PR — review by hand"


def Run(args, cwd=None, check=False):
	"""Run a command and return (returncode, stdout). stderr is folded away."""
	result = subprocess.run(
		args, cwd=cwd, capture_output=True, text=True, check=False)
	if check and result.returncode != 0:
		raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
	return result.returncode, result.stdout


def GetRepoRoot(start):
	"""Resolve the main checkout's root, refusing to run from inside a worktree."""
	code, top = Run(["git", "-C", start, "rev-parse", "--show-toplevel"])
	if code != 0:
		raise RuntimeError(f"not a git repository: {start}")
	top = top.strip()
	_, git_dir = Run(["git", "-C", top, "rev-parse", "--absolute-git-dir"])
	_, common = Run(["git", "-C", top, "rev-parse", "--path-format=absolute",
	                 "--git-common-dir"])
	if Path(git_dir.strip()).resolve() != Path(common.strip()).resolve():
		raise RuntimeError(
			f"{top} is itself a worktree; run this from the main checkout "
			f"({Path(common.strip()).parent})")
	return top


def GetWorktrees(repo):
	"""Parse `git worktree list --porcelain` into a list of dicts."""
	_, out = Run(["git", "-C", repo, "worktree", "list", "--porcelain"], check=True)
	entries, current = [], {}
	for line in out.splitlines():
		if not line.strip():
			if current:
				entries.append(current)
				current = {}
			continue
		key, _, value = line.partition(" ")
		if key in PORCELAIN_FLAGS:
			current[key] = value or True
		elif key == "branch":
			current["branch"] = re.sub(r"^refs/heads/", "", value)
		else:
			current[key] = value
	if current:
		entries.append(current)
	return entries


def GetLiveDirectories():
	"""Map every readable process cwd to its pid, so live trees are never removed.

	A background session or a running build holds its worktree as cwd. Reading
	/proc is best-effort: other users' processes raise and are skipped, which
	is why this is one guard among several rather than the only one.
	"""
	live = {}
	proc = Path("/proc")
	if not proc.is_dir():
		return live
	for entry in proc.iterdir():
		if not entry.name.isdigit():
			continue
		try:
			target = os.readlink(entry / "cwd")
		except OSError:
			continue
		live.setdefault(target, entry.name)
	return live


def FindBuildLock(path):
	"""Return the first Forge lock file under a worktree, or None.

	A killed build leaves forge.lock behind for up to two hours; removing the
	tree under a live builder would strand it mid-write.
	"""
	forge = Path(path) / "Applications" / "Forge"
	if not forge.is_dir():
		return None
	for lock in forge.glob("**/forge.lock"):
		return str(lock.relative_to(path))
	return None


def IsAncestor(repo, ref, upstream):
	code, _ = Run(["git", "-C", repo, "merge-base", "--is-ancestor", ref, upstream])
	return code == 0


def GetUpstreamTrack(repo, branch):
	"""Return (upstream_name, track_string) for a branch; ('', '') when unset."""
	_, out = Run(["git", "-C", repo, "for-each-ref",
	              "--format=%(upstream:short)%09%(upstream:track)",
	              f"refs/heads/{branch}"])
	name, _, track = out.strip().partition("\t")
	return name, track


def GetMergedHeads(repo, limit=MERGED_PR_WINDOW):
	"""Map head branch -> PR number over the most recent merged PRs.

	One query covers the whole sweep. Returns None when gh is unavailable or
	unauthenticated, which the caller must treat as "cannot verify", never as
	"nothing merged".
	"""
	code, out = Run(["gh", "pr", "list", "--state", "merged", "--json",
	                 "number,headRefName", "--limit", str(limit)], cwd=repo)
	if code != 0:
		return None
	try:
		found = json.loads(out or "[]")
	except json.JSONDecodeError:
		return None
	return {pr["headRefName"]: pr["number"] for pr in found}


def GetMergedPullRequest(repo, branch):
	"""Look up one branch's merged PR, for heads older than the bulk window."""
	code, out = Run(["gh", "pr", "list", "--head", branch, "--state", "merged",
	                 "--json", "number", "--limit", "1"], cwd=repo)
	if code != 0:
		return None
	try:
		found = json.loads(out or "[]")
	except json.JSONDecodeError:
		return None
	return found[0]["number"] if found else None


def Classify(repo, entry, upstream, live, merged_heads, trust_gone):
	"""Return (removable, reason) for one worktree entry."""
	path = entry["worktree"]
	if Path(path).resolve() == Path(repo).resolve():
		return False, KEEP_MAIN
	if "locked" in entry:
		return False, KEEP_LOCKED
	for cwd, pid in live.items():
		if cwd == path or cwd.startswith(path.rstrip("/") + "/"):
			return False, KEEP_IN_USE.format(pid=pid)
	lock = FindBuildLock(path)
	if lock:
		return False, KEEP_BUILD_LOCK.format(lock=lock)

	# --porcelain alone counts ignored build output as clean, which is what we
	# want: .forge trees are regeneratable and must not pin a landed worktree.
	code, status = Run(["git", "-C", path, "status", "--porcelain"])
	if code != 0:
		return False, "git status failed"
	if status.strip():
		return False, KEEP_DIRTY.format(count=len(status.strip().splitlines()))

	branch = entry.get("branch")
	if not branch:
		return False, KEEP_DETACHED

	# Ancestry is the only cryptographic proof, so it is checked first and needs
	# no network. Phoenix squash-merges, so it fires rarely.
	if IsAncestor(repo, f"refs/heads/{branch}", upstream):
		return True, LANDED_ANCESTOR.format(upstream=upstream)

	# A deleted remote branch is a hint, not proof: closing a PR unmerged deletes
	# the branch too. A merged PR for this head is the evidence that settles it.
	if merged_heads is not None:
		number = merged_heads.get(branch) or GetMergedPullRequest(repo, branch)
		if number:
			return True, LANDED_PR.format(number=number)

	name, track = GetUpstreamTrack(repo, branch)
	if name and "gone" in track:
		if trust_gone:
			return True, LANDED_GONE
		return False, KEEP_GONE_UNMERGED

	_, ahead = Run(["git", "-C", repo, "rev-list", "--count",
	                f"{upstream}..refs/heads/{branch}"])
	return False, KEEP_UNPUSHED.format(count=ahead.strip() or "?", upstream=upstream)


def GetSize(path):
	code, out = Run(["du", "-sx", "--block-size=1", path])
	if code != 0:
		return 0
	return int(out.split("\t", 1)[0] or 0)


def FormatBytes(count):
	for unit in ("B", "K", "M", "G", "T"):
		if count < 1024 or unit == "T":
			return f"{count:.0f}{unit}" if unit == "B" else f"{count:.1f}{unit}"
		count /= 1024
	return f"{count:.1f}T"


def Remove(repo, entry, delete_branch):
	"""Remove one worktree and, when asked, its landed branch. Returns an error or None."""
	path = entry["worktree"]
	# No --force: git refuses a tree that turned dirty since classification,
	# which closes the window between the check above and this call.
	code, _ = Run(["git", "-C", repo, "worktree", "remove", path])
	if code != 0:
		return f"worktree remove refused: {path}"
	branch = entry.get("branch")
	if delete_branch and branch:
		code, _ = Run(["git", "-C", repo, "branch", "-D", branch])
		if code != 0:
			return f"branch delete refused: {branch}"
	return None


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo", default=".", help="main checkout (default: cwd)")
	parser.add_argument("--upstream", default=DEFAULT_UPSTREAM,
	                    help=f"ref a branch must have landed on (default: {DEFAULT_UPSTREAM})")
	parser.add_argument("--apply", action="store_true",
	                    help="actually remove; without it nothing is deleted")
	parser.add_argument("--limit", type=int, default=0,
	                    help="act on at most N worktrees (0 = no limit)")
	parser.add_argument("--no-fetch", action="store_true",
	                    help="skip `git fetch --prune` (upstream 'gone' will be stale)")
	parser.add_argument("--no-gh", action="store_true",
	                    help="do not consult GitHub; only ancestry can prove a landing")
	parser.add_argument("--trust-gone", action="store_true",
	                    help="treat a deleted remote branch as proof of landing, "
	                         "without a merged PR to confirm it")
	parser.add_argument("--keep-branches", action="store_true",
	                    help="remove the worktree but leave its landed branch")
	parser.add_argument("--sizes", action="store_true",
	                    help="measure disk per candidate (slow on large trees)")
	parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
	args = parser.parse_args()

	try:
		repo = GetRepoRoot(args.repo)
	except RuntimeError as error:
		print(f"error: {error}", file=sys.stderr)
		return 2

	if not args.no_fetch:
		code, _ = Run(["git", "-C", repo, "fetch", "--prune"])
		if code != 0:
			print("error: fetch --prune failed; upstream state would be stale",
			      file=sys.stderr)
			return 2

	code, _ = Run(["git", "-C", repo, "rev-parse", "--verify", args.upstream])
	if code != 0:
		print(f"error: no such ref: {args.upstream}", file=sys.stderr)
		return 2

	merged_heads = None if args.no_gh else GetMergedHeads(repo)
	if merged_heads is None and not args.no_gh and not args.trust_gone:
		print("warning: gh unavailable — a branch can only be proven landed by "
		      "ancestry. Pass --trust-gone to accept a deleted remote branch "
		      "as evidence.", file=sys.stderr)

	live = GetLiveDirectories()
	rows = []
	for entry in GetWorktrees(repo):
		if "bare" in entry:
			continue
		removable, reason = Classify(repo, entry, args.upstream, live,
		                             merged_heads, args.trust_gone)
		rows.append({
			"path": entry["worktree"],
			"branch": entry.get("branch", ""),
			"removable": removable,
			"reason": reason,
		})

	removable = [row for row in rows if row["removable"]]
	candidates = removable[:args.limit] if args.limit else removable
	if args.sizes:
		for row in candidates:
			row["bytes"] = GetSize(row["path"])

	removed, failures = [], []
	if args.apply:
		by_path = {entry["worktree"]: entry for entry in GetWorktrees(repo)}
		for row in candidates:
			error = Remove(repo, by_path[row["path"]], not args.keep_branches)
			(failures if error else removed).append(error or row)
		Run(["git", "-C", repo, "worktree", "prune"])

	if args.json:
		print(json.dumps({
			"repo": repo, "upstream": args.upstream, "applied": args.apply,
			"worktrees": rows, "removed": [row["path"] for row in removed],
			"failures": failures,
		}, indent=2))
		return 1 if failures else 0

	kept = [row for row in rows if not row["removable"]]
	for row in sorted(rows, key=lambda row: (not row["removable"], row["path"])):
		mark = "REMOVE" if row["removable"] else "keep  "
		size = f"  {FormatBytes(row['bytes'])}" if row.get("bytes") else ""
		print(f"{mark}  {row['branch'] or '(detached)':<62}  {row['reason']}{size}")

	total = sum(row.get("bytes", 0) for row in candidates)
	limited = f", {len(candidates)} selected by --limit" if len(candidates) != len(removable) else ""
	print(f"\n{len(rows)} worktrees: {len(removable)} removable, {len(kept)} kept{limited}"
	      + (f", {FormatBytes(total)} reclaimable" if total else ""))
	if args.apply:
		print(f"removed {len(removed)}"
		      + (f", {len(failures)} failed" if failures else ""))
		for failure in failures:
			print(f"  {failure}", file=sys.stderr)
	else:
		print("dry run — nothing deleted. Re-run with --apply.")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
