# CI Watch Protocol

After a PR is pushed in `/phoe:implement` or `/phoe:execute`, run this passive
CI watch loop so the user can come back to a still-warm prompt cache and merge
without paying a fresh-context re-read. Without it, the agent goes idle right
after `gh pr create`, the 5-minute prompt-cache TTL expires, and the next user
turn (the merge) bills full context.

## When to engage

Mandatory after any PR push -- the watch keeps the prompt cache warm so the
user can merge without a fresh-context re-read. Refer to each PR as `PR #<N>`
throughout (captured at `gh pr create` time in `/phoe:implement` Step 16 and
`/phoe:execute` Step 4h).

- **`/phoe:implement`** -- run after Step 16, once, against the PR #<N> just opened.
- **`/phoe:execute`** -- run after Step 6, against every `PR #<N>` opened this
  run. Multiple PRs: watch collectively (see "Multiple PRs" below).
- **Skip ONLY when:** push declined (no PR), CI already all green at push time,
  or user explicitly disabled the watch. Anything else -- run the watch.

## Loop budget

- **Initial timer:** 270 seconds.
- **Snoozes:** up to 3. After the third snooze the watch ends regardless of CI
  state.
- **Total checks:** up to 4 (one initial + three snoozes).
- **Total wall time:** up to ~18 minutes.

The 270-second figure is deliberate: it sits just inside the 5-minute prompt
cache TTL, so each iteration replays the conversation cached. **Do not extend
past 270.** If the check is slow, run it inline -- do not pad the sleep
to compensate.

## Sleep mechanics

Each timer is a single `Bash` call:

```bash
sleep 270
```

Use a Bash tool `timeout` of `290000` ms (290 s) to leave headroom. Do not
break the sleep into shorter polls; the goal is one clean cache-friendly
block per iteration.

## Per-iteration check

The session's token often lacks `checks:read`, so `gh pr checks` / `statusCheckRollup` return
`Resource not accessible by personal access token` (the PR shows UNSTABLE). Use the **Actions runs
API**, which the token *can* read. Resolve the PR's head branch once, then list its workflow runs:

```bash
BRANCH=$(gh pr view <PR_URL> --json headRefName -q .headRefName)
gh run list --branch "$BRANCH" --json databaseId,name,status,conclusion --limit 20
```

Classify each run:

- **passed** -- `status == "completed"` and `conclusion == "success"`
- **failed** -- `status == "completed"` and `conclusion` is one of `failure`,
  `cancelled`, `timed_out`, `action_required`
- **pending** -- everything else (`queued`, `in_progress`, `requested`, etc.)

Roll up to a single PR-level state:

- **READY** -- every run completed and passed.
- **FAILED** -- at least one run failed. Pull the failing log without a re-run via
  `gh run view <databaseId> --log-failed`.
- **PENDING** -- otherwise.

(If `gh pr checks` happens to work in your environment — a token *with* `checks:read` — it is a
fine shortcut, but never depend on it; the `gh run` path is the reliable one here.)

## Flashy messages

Every iteration emits a **terminal bell** plus a clearly-formatted status
block. The bell is the ping; the markdown is the colorful part. Keep the
format consistent so the user can scan it at a glance across iterations.

Ring the bell with a single Bash call before each message:

```bash
printf '\a'
```

`\a` is plain ASCII (BEL, byte 7), not a unicode character.

If `PushNotification` is available, also fire one for stronger user attention
on terminal states (READY, FAILED, expired). Skip it for in-progress
iterations -- a bell is enough.

### Message templates

Use these exact headings so they are visually consistent across runs.

**Iteration K (PENDING, K in 1..4):**

```
## CI Watch -- PR #<N> -- check <K>/4 -- PENDING

Pending: <comma-separated list of check names still running>
Passed:  <count>
Failed:  <count or "none">

Sleeping 270s before the next check.
```

**READY:**

```
## CI Watch -- PR #<N> -- READY FOR MERGE

All <count> checks passed.
PR: <URL>

Cache is warm. Review and merge now to avoid a fresh-context re-read.
```

**FAILED:**

```
## CI Watch -- PR #<N> -- CI FAILED

Failed checks:
- <name>: <conclusion>
- <name>: <conclusion>

PR: <URL>
```

**Watch expired (still PENDING after the third snooze):**

```
## CI Watch -- PR #<N> -- watch expired after 3 snoozes

Last status: <comma-separated pending check names>
Reconnect manually: gh run list --branch <branch>
```

## Multiple PRs (`/phoe:execute`)

When a run opens more than one PR, watch them collectively in a single loop:

1. On each iteration, run the per-iteration check (resolve each PR's branch, then
   `gh run list --branch "$BRANCH"`) against every PR.
2. Roll up to a wave-level state:
   - **ANY READY** -- at least one PR has all checks passed. Exit the watch
     and emit the READY message naming which PRs are ready (so the user can
     start merging).
   - **ALL FAILED** -- every PR has at least one failed check. Exit and
     report.
   - **MIXED PENDING** -- otherwise. Snooze.
3. The PENDING message lists per-PR status as a compact table:

```
## CI Watch -- /phoe:execute (<count> PRs) -- check <K>/4 -- PENDING

| PR  | Status  | Pending checks    |
|-----|---------|-------------------|
| #<N1> | PENDING | build, test     |
| #<N2> | READY   | --              |
| #<N3> | FAILED  | lint            |

Sleeping 270s before the next check.
```

If the wave reaches "ANY READY" early, exit immediately -- the user wants to
start merging while the cache is warm, not wait for the slowest PR.

## Auto mode

The watch is consistent with auto mode: it is a passive timer, not a
question, and it does not require user input. It always runs after a
successful PR push from `/phoe:implement` or `/phoe:execute` unless one of
the skip conditions above applies.
