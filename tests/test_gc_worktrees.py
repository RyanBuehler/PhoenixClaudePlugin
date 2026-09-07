#!/usr/bin/env python3
"""Unit tests for scripts/gc_worktrees.py.

Every case builds a real git repository with real worktrees. The guards this
script relies on are git behaviors, so a mocked git would prove nothing.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gc_worktrees.py"


def Git(cwd, *args):
	return subprocess.run(
		["git", "-C", str(cwd), *args],
		capture_output=True, text=True, check=True).stdout


class GcTestCase(unittest.TestCase):
	"""Base — one origin/clone pair per test, with main already published."""

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		root = Path(self._tmp.name)
		self.origin = root / "origin.git"
		self.repo = root / "clone"
		subprocess.run(["git", "init", "--bare", "-b", "main", str(self.origin)],
		               capture_output=True, check=True)
		subprocess.run(["git", "clone", str(self.origin), str(self.repo)],
		               capture_output=True, check=True)
		Git(self.repo, "config", "user.name", "Test")
		Git(self.repo, "config", "user.email", "test@example.com")
		(self.repo / "README").write_text("seed\n")
		Git(self.repo, "add", "README")
		Git(self.repo, "commit", "-m", "seed")
		Git(self.repo, "push", "-u", "origin", "main")

	def tearDown(self):
		self._tmp.cleanup()

	def MakeWorktree(self, branch, path=None):
		"""Create a worktree on a new branch off the current origin/main."""
		path = self.repo / ".claude" / "worktrees" / (path or branch.replace("/", "-"))
		Git(self.repo, "fetch", "origin")
		Git(self.repo, "worktree", "add", str(path), "-b", branch, "origin/main")
		return path

	def Commit(self, worktree, text):
		(worktree / "work.txt").write_text(text)
		Git(worktree, "add", "work.txt")
		Git(worktree, "commit", "-m", text)

	def Run(self, *extra):
		"""Run the script over the fixture repo, returning the completed process."""
		return subprocess.run(
			["python3", str(SCRIPT), "--repo", str(self.repo), "--json", *extra],
			capture_output=True, text=True)

	def Gc(self, *extra):
		"""Run with GitHub disabled — the fixture remote is a local bare repo."""
		result = self.Run("--no-gh", *extra)
		self.assertIn(result.returncode, (0, 1), result.stderr)
		return json.loads(result.stdout)

	def Row(self, report, branch):
		for row in report["worktrees"]:
			if row["branch"] == branch:
				return row
		self.fail(f"no row for {branch}; got {[r['branch'] for r in report['worktrees']]}")


class ClassificationTests(GcTestCase):

	def test_branch_merged_into_main_is_removable(self):
		worktree = self.MakeWorktree("challenge/landed")
		self.Commit(worktree, "landed work")
		Git(worktree, "push", "origin", "HEAD:refs/heads/main")
		report = self.Gc()
		row = self.Row(report, "challenge/landed")
		self.assertTrue(row["removable"], row["reason"])
		self.assertIn("merged into", row["reason"])

	def test_branch_with_unique_commits_is_kept(self):
		worktree = self.MakeWorktree("challenge/unlanded")
		self.Commit(worktree, "work that exists nowhere else")
		row = self.Row(self.Gc(), "challenge/unlanded")
		self.assertFalse(row["removable"])
		self.assertIn("not on origin/main", row["reason"])

	def MakeGoneUpstreamWorktree(self, branch="challenge/squashed"):
		"""A branch whose remote head was deleted — squash-merged, or closed unmerged."""
		worktree = self.MakeWorktree(branch)
		self.Commit(worktree, "work")
		Git(worktree, "push", "-u", "origin", branch)
		Git(self.repo, "push", "origin", "--delete", branch)
		return worktree

	def test_gone_upstream_alone_is_not_proof_of_landing(self):
		"""Closing a PR unmerged also deletes the branch, so 'gone' cannot stand alone."""
		self.MakeGoneUpstreamWorktree()
		row = self.Row(self.Gc(), "challenge/squashed")
		self.assertFalse(row["removable"], row["reason"])
		self.assertEqual(row["reason"],
		                 "upstream gone but no merged PR — review by hand")

	def test_trust_gone_accepts_a_deleted_remote_branch(self):
		self.MakeGoneUpstreamWorktree()
		row = self.Row(self.Gc("--trust-gone"), "challenge/squashed")
		self.assertTrue(row["removable"], row["reason"])
		self.assertEqual(row["reason"], "landed: upstream gone (unverified)")
		self.assertNotIn("merged into", row["reason"],
		                 "a squashed branch must not be judged by ancestry")

	def test_unverifiable_github_warns_and_keeps(self):
		"""gh cannot answer for a local bare remote; that must not read as 'not merged'."""
		self.MakeGoneUpstreamWorktree()
		result = self.Run()
		self.assertIn("gh unavailable", result.stderr)
		row = self.Row(json.loads(result.stdout), "challenge/squashed")
		self.assertFalse(row["removable"])

	def test_uncommitted_changes_keep_a_landed_worktree(self):
		worktree = self.MakeWorktree("challenge/dirty")
		(worktree / "scratch.txt").write_text("unsaved\n")
		row = self.Row(self.Gc(), "challenge/dirty")
		self.assertFalse(row["removable"])
		self.assertIn("uncommitted", row["reason"])

	def test_locked_worktree_is_kept(self):
		worktree = self.MakeWorktree("challenge/locked")
		Git(self.repo, "worktree", "lock", str(worktree))
		row = self.Row(self.Gc(), "challenge/locked")
		self.assertFalse(row["removable"])
		self.assertEqual(row["reason"], "locked")

	def test_forge_lock_keeps_a_landed_worktree(self):
		worktree = self.MakeWorktree("challenge/building")
		lock = worktree / "Applications" / "Forge" / ".forge" / "editor-debug"
		lock.mkdir(parents=True)
		(lock / "forge.lock").write_text("held\n")
		row = self.Row(self.Gc(), "challenge/building")
		self.assertFalse(row["removable"])
		self.assertIn("build lock held", row["reason"])

	def test_live_process_cwd_keeps_a_landed_worktree(self):
		worktree = self.MakeWorktree("challenge/live")
		held = subprocess.Popen(["sleep", "30"], cwd=str(worktree))
		try:
			row = self.Row(self.Gc(), "challenge/live")
		finally:
			held.kill()
			held.wait()
		self.assertFalse(row["removable"])
		self.assertIn("in use by pid", row["reason"])

	def test_detached_head_worktree_is_kept(self):
		path = self.repo / ".claude" / "worktrees" / "detached"
		Git(self.repo, "worktree", "add", "--detach", str(path), "main")
		row = next(r for r in self.Gc()["worktrees"] if str(path) == r["path"])
		self.assertFalse(row["removable"])
		self.assertEqual(row["reason"], "detached HEAD")

	def test_main_checkout_is_never_removable(self):
		report = self.Gc()
		row = next(r for r in report["worktrees"]
		           if Path(r["path"]).resolve() == self.repo.resolve())
		self.assertFalse(row["removable"])
		self.assertEqual(row["reason"], "main checkout")


class ApplyTests(GcTestCase):

	def test_apply_removes_only_the_landed_worktree(self):
		landed = self.MakeWorktree("challenge/landed")
		self.Commit(landed, "landed work")
		Git(landed, "push", "origin", "HEAD:refs/heads/main")
		kept = self.MakeWorktree("challenge/kept")
		self.Commit(kept, "unique work")

		report = self.Gc("--apply")
		self.assertEqual(report["removed"], [str(landed)])
		self.assertEqual(report["failures"], [])
		self.assertFalse(landed.exists())
		self.assertTrue(kept.exists())

		branches = Git(self.repo, "branch", "--format=%(refname:short)").split()
		self.assertNotIn("challenge/landed", branches)
		self.assertIn("challenge/kept", branches)

	def test_keep_branches_leaves_the_branch_behind(self):
		landed = self.MakeWorktree("challenge/landed")
		self.Commit(landed, "landed work")
		Git(landed, "push", "origin", "HEAD:refs/heads/main")
		self.Gc("--apply", "--keep-branches")
		self.assertFalse(landed.exists())
		branches = Git(self.repo, "branch", "--format=%(refname:short)").split()
		self.assertIn("challenge/landed", branches)

	def test_limit_caps_how_many_are_removed(self):
		for index in range(3):
			worktree = self.MakeWorktree(f"challenge/landed-{index}")
			self.Commit(worktree, f"work {index}")
			Git(worktree, "push", "origin", "HEAD:refs/heads/main")
		report = self.Gc("--apply", "--limit", "1")
		self.assertEqual(len(report["removed"]), 1)

	def test_dry_run_removes_nothing(self):
		landed = self.MakeWorktree("challenge/landed")
		self.Commit(landed, "landed work")
		Git(landed, "push", "origin", "HEAD:refs/heads/main")
		report = self.Gc()
		self.assertEqual(report["removed"], [])
		self.assertTrue(landed.exists())


class GuardTests(GcTestCase):

	def test_refuses_to_run_from_inside_a_worktree(self):
		worktree = self.MakeWorktree("challenge/inside")
		result = subprocess.run(
			["python3", str(SCRIPT), "--repo", str(worktree), "--json"],
			capture_output=True, text=True)
		self.assertEqual(result.returncode, 2)
		self.assertIn("itself a worktree", result.stderr)

	def test_missing_upstream_ref_aborts(self):
		result = subprocess.run(
			["python3", str(SCRIPT), "--repo", str(self.repo),
			 "--upstream", "origin/nonexistent", "--json"],
			capture_output=True, text=True)
		self.assertEqual(result.returncode, 2)
		self.assertIn("no such ref", result.stderr)


if __name__ == "__main__":
	unittest.main()
