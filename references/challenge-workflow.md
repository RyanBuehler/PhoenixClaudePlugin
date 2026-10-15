# Challenge workflow

Steps shared by `/phoe:implement`, `/phoe:bugfix` and `/phoe:execute`. `<kind>` is `challenge` or
`bug`. The branch is `<kind>/<branch-label>` in `.claude/worktrees/<kind>-<branch-label>`, where
`<branch-label>` is the Crucible label cut to the 40-character cap (`references/core-rules.md`
§Branches and worktrees; the hook's refusal names the shortened branch). `--label=` arguments and the PR's
`Crucible:` line keep the full label.

## Contents

1. Bootstrap
2. Detect landed items in review
3. Claim and worktree
4. Acceptance criteria
5. Publish
6. Reconcile siblings and docs
7. After landing
8. Feedback log
9. Confirm new names

## 1. Bootstrap

1. Run `/phoe:build crucible` (builds `crucible` and `crucible-server`; a no-op when current). On a
   version mismatch, stop and report it.
2. Resolve the CLI in every Bash block that calls it. Each block is a fresh shell, and the script
   finds the main checkout's binary from inside a worktree too:
   ```bash
   CRUCIBLE=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crucible_path.py) || exit 1
   "$CRUCIBLE" status
   ```
   The server is user-managed: do not start it. If the CLI cannot reach it, report that and stop.
3. Fetch, never pull. Local `main` is never checked out or written, because parallel sessions
   share it; work from `origin/main`.
   ```bash
   git ls-remote --exit-code origin HEAD >/dev/null 2>&1 && git fetch origin main
   ```
   If origin is unreachable (common in sandboxed containers without credentials), warn once
   ("origin unreachable; working from local main"), read `main` wherever these steps say
   `origin/main`, and continue without retrying.

## 2. Detect landed items in review

Crucible does not notice merges. Before picking the next item, check each one in `review`:

```bash
"$CRUCIBLE" --json <kind> list --status=review
git fetch origin main
gh pr view <review-link-or-branch> --json number,state,mergeCommit
```

An item has **landed** when its PR's `state` is `MERGED` and
`git merge-base --is-ancestor <merge-sha> origin/main` succeeds (a stack layer can read `MERGED`
after landing in its parent branch, not main). Then run §7 without asking, starting with marking it
merged: tracking follows reality, and saga progress counts only `merged`. Anything else (open PR, closed
unmerged, branch gone) stays in `review`. With no PR to check, a commit on `origin/main` naming the
label is evidence to show the user, not proof.

## 3. Claim and worktree

1. `"$CRUCIBLE" <kind> show --label=<LABEL>`; confirm it is still `todo`, since a parallel session
   may have claimed it.
2. Claim it before creating anything, so a parallel session cannot take it:
   `"$CRUCIBLE" <kind> move --label=<LABEL> active`. If you drop it later, move it back to `todo`.
3. From the main repo root:
   ```bash
   git worktree add .claude/worktrees/<kind>-<branch-label> -b <kind>/<branch-label> <base-ref>
   ```
   `<base-ref>` is `origin/main` unless the skill says otherwise. `git worktree add -b` is the only
   way to create a branch: `branch-worktree-check.py` blocks `git checkout -b`, `git switch -c` and
   `git branch <name>`, and requires the folder to be the branch with `/` as `-`. Do not use
   `EnterWorktree(name=...)`, which picks its own name and base.
4. Enter it with `EnterWorktree(path=<absolute path>)`. In a background session the isolation guard
   refuses native `Write`/`Edit` in a worktree the session has not entered; entering by path keeps
   them working and takes no removal ownership. A relative path resolves against the current
   directory, so from inside one worktree it names a nested one. Nothing stops edits to a previous
   worktree: `ExitWorktree(keep)` before entering the next.
5. Bootstrap Forge, which a fresh worktree lacks (`Applications/Forge/.bootstrap-out/forge`):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/forge_wait.py start --log <worktree>/.forge-wait/bootstrap.log -- python3 <worktree>/Applications/Forge/Scripts/bootstrap.py
   ```
   Run it in the foreground with `timeout: 600000` and repeat the `wait --log ...` call it prints
   until it reports `exited 0`; do not watch the log. Do not edit the tree or start a build until it
   exits: it bakes the on-disk tree into its binary, and a build against an unfinished bootstrap
   fails with `No such file or directory`, which reads like a broken tree.

## 4. Acceptance criteria

Before review, answer for each criterion from `<kind> show`:

- **Met?** Yes, no or partly.
- **Evidence:** file:line, trial name or command output.
- **Unverifiable?** Flag it for the user (e.g. "feels responsive").

Fix what is unmet and verify again. Check that new public interfaces and non-trivial logic have
trials. Then ask whether each criterion is still the right ask, given the code as it is; a criterion
written before the code was read is a hypothesis. Stop and report a **re-cut candidate**, quoting
the wording, when a criterion:

- names state a placeholder type cannot carry (encoding the absence is the larger diff, thrown away
  when the placeholder is filled in);
- names a consumer that does not exist yet, such as a later challenge in the saga (do not claim it
  met against a stand-in);
- can be met by something obviously wrong: freezing, hiding or disabling the thing it is about.

Do not silently pick the stronger reading of an ambiguous design doc; that is the owner's question.

## 5. Publish

`push-gate.py` checks git identity and credentials; pushing and opening a PR need no confirmation.

```bash
git push -u origin <kind>/<branch-label>
PR_URL=$(gh pr create --head <kind>/<branch-label> --base main --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-4 bullets: what the branch does; for a bug, the bug, its root cause and the fix>

Crucible: #<id> <label>
Saga: #<saga-id> <saga-label>
EOF
)")
echo "Opened PR #${PR_URL##*/}: ${PR_URL}"
"$CRUCIBLE" <kind> update --label=<LABEL> --replace-review-link="${PR_URL}"
```

- The trailers are mandatory. Drop `Saga:` for an orphan or a bug. A PR carrying several items lists
  them all (`Crucible: #<id-1> <label-1>, #<id-2> <label-2>`) and records the link on each.
- Trust output, not exit codes. `gh pr create` can fail with HTTP 503 after creating the PR, so grep
  its output for a URL and check `gh pr list --head <branch>` before retrying; a blind retry
  duplicates the PR. `git ls-remote origin <branch>` says whether a push landed; the
  `origin/<branch>` tracking ref can be stale.
- Call it **PR #<N>** in narration and reports, never a bare URL.
- Then remove only the worktree (`ExitWorktree(keep)` first if you are in it). The branches carry the
  open PR. Later fixes for review comments, conflicts or CI use `/phoe:pr-fixup`.

## 6. Reconcile siblings and docs

Work can leave later challenges and design docs naming things it renamed. Two passes: pre-merge,
against the committed diff once review passes, and the authoritative pass against the merged diff
(§7). This step edits metadata and docs only, never the implementation.

1. List the open siblings after this one (`"$CRUCIBLE" --json saga show --label=<SAGA_LABEL>`, todo
   and blocked; none for an orphan), read each (`challenge show --label=<SIBLING>`), and grep the
   `docs/` design and spec files.
2. Look for renamed types, functions or files; moved or split files; changed signatures or
   parameters; shifted module boundaries; replaced concepts.
3. Fix only what is stale: `"$CRUCIBLE" challenge update --label=<SIBLING> --<field>=...`
   (`--help` lists the fields). A doc fix rides this branch pre-merge; post-merge the branch is gone,
   so file a docs-reconcile challenge with `/phoe:plan`.
4. Comment on every open challenge, sibling or orphan, whose ground the work moved:
   `"$CRUCIBLE" challenge comment --label=<OTHER> --body="<what moved to what; behaviors since that must not be dropped>"`.
   The edit fixes the words; only the comment tells its implementer the ground moved.
5. A sibling whose scope is broken, not merely renamed, is not rewritten: flag it for re-plan (and
   block it post-merge).
6. Report which siblings and docs changed (and which fields), or "none stale". The line is required,
   so a skipped pass shows.

## 7. After landing

Whichever session proves landing (§2) does this, usually not the one that opened the PR.

1. `"$CRUCIBLE" <kind> move --label=<LABEL> merged`. This archives it;
   `<kind> unarchive --label=<LABEL>` restores it to `todo`.
2. Run §6 against the merged diff.
3. If an open PR is based on this branch (`gh pr list --base <kind>/<branch-label>`), retarget it
   (`gh pr edit <N> --base main`) and mark it ready (`gh pr ready <N>`) before deleting the branch.
4. Clean up from the main checkout per `references/concluding-work.md`, skipping what is gone
   (`ExitWorktree(keep)` first if you are in the worktree):
   ```bash
   git worktree remove .claude/worktrees/<kind>-<branch-label>
   git branch -D <kind>/<branch-label>
   git push origin --delete <kind>/<branch-label>
   git fetch --prune origin
   ```

## 8. Feedback log

Collect every subagent's `## Workflow Friction` section and add your own: what slowed this run
(missing context, ambiguous spec, undocumented convention, tooling or guard trouble, context
bloat). If every section is `none`, write nothing. Otherwise copy the items verbatim, without
summarizing or filtering, and omit agents that reported `none`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/append_feedback.py --run "/phoe:<skill> <args>" <<'EOF'
### Orchestrator
- <item>

### Challenge: <label> (adversarial-reviewer)
- <item>
EOF
```

Head your own section with your role (`Orchestrator`, `Implementer`) and each subagent's as
`<Kind>: <label> (<role>)`, where the role is implementer, test-engineer, spec-reviewer,
quality-reviewer, adversarial-reviewer or `fix pass, round <N>`. The script adds the
`## <date> - <run>` heading and appends to `.claude/AGENT_FEEDBACK.md` in the main checkout
(resolved from git, so it works from a worktree), creating the log if needed and never rewriting
earlier entries. Use it rather than `Write`/`Edit`, which the isolation guard can refuse in a
background session; `hooks/bash-guard.py` has no heredoc rule.

## 9. Confirm new names

Keep implementing with your best name, then get Ryan's confirmation before the final verify, so the
verify covers any rename. This covers names the work adds to production code (types, functions,
modules, flags, JSON keys, refusal text). Names used only in trials need no confirmation.

1. Collect each name with what it names and its runner-up (an implementer reports them under
   `## Names Pending Confirmation`).
2. Optionally dispatch one read-only Sonnet subagent (`model: "sonnet"`) with that list,
   `Docs/StyleGuide.md` §Naming a new symbol and `Docs/Lexicon.md`, to recommend the best name for
   each.
3. Ask Ryan with AskUserQuestion, public and wire-visible names first, the best candidate as the
   recommended option.
4. Apply each rename on the branch by hand, never with a bulk regex. A name added by a later review
   fix is confirmed the same way before the push; rebuild and re-run the trials it touches.
