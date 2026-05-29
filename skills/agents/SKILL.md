---
name: agents
description: Use to answer "which background job owns PR #X?" or "which PRs is job Y juggling?" — looks up the PR/job/session registry written by the agent-registry-tracker hook. Activates on phrases like "who owns PR 1234", "which agent made this PR", "list live agents", or any cross-reference between `claude agents` background jobs and GitHub PRs.
---

# Agent ↔ PR Registry

The `agent-registry-tracker.py` PostToolUse hook silently records every `gh pr create` and `gh pr edit` it sees, writing one JSON object per line to:

```
~/.claude/agent-registry.jsonl
```

This skill is what you read before answering any question about who is working on what PR. It is read-only — never edit the registry.

## Hard rules

- **Use `query.py`, not raw `cat` or `jq`.** The query script handles latest-entry-wins, joins with the live job list, and formats output consistently. Hand-rolled `jq` pipelines have gotten the answer wrong before.
- **Never write to the registry.** It is append-only and owned by the hook. If an entry is wrong, leave it — newer entries win.
- **Treat the registry as best-effort, not authoritative.** It only sees PRs created or edited via `gh pr create` / `gh pr edit`. PRs created from the web UI, `gh api`, or directly via curl will not appear. If a user asks about a PR that isn't in the registry, say so plainly — don't guess.

## The query script

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agents/query.py <subcommand> [args]
```

`${CLAUDE_PLUGIN_ROOT}` resolves to the plugin install path. If running outside a plugin context (e.g. debugging), use the literal path under `~/phoenixclaudeplugin/`.

| Subcommand | What it answers |
|---|---|
| `pr <number>` | Every recorded event for PR #N, chronologically. Shows whether the owning job is still alive. |
| `job <id>` | Every PR a background job has touched (latest entry per PR). Also reports whether the job's directory still exists. |
| `session <id>` | Every PR a session id has touched. Use when only the session id is known (interactive sessions don't have a job id). |
| `list` | Latest entry for every tracked PR, newest first. Add `--alive-only` to filter to PRs owned by live background jobs. |
| `raw` | Print the registry verbatim. Use for debugging the tracker, never for answering user questions. |

## How to answer common questions

### "Which job has PR #1234?"

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agents/query.py pr 1234
```

Read the output: if multiple entries exist, the latest `job_id` is the current owner. If the job is reported `(gone)`, the job has already been deleted — the PR is unowned.

### "What is job 9271caec working on?"

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agents/query.py job 9271caec
```

Output lists every PR the job has created or edited. A job with multiple PRs is the case the user explicitly flagged as risky — surface the count clearly so they don't close the job prematurely.

### "List all live agents and their PRs."

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/agents/query.py list --alive-only
```

Group output by `job_id` in your reply so the user can see who is multi-tasking.

### "Is PR #1234 abandoned?"

Run `pr 1234`. If the latest entry's job is `(gone)` and the PR is still open on GitHub, it's orphaned — the agent was killed before merge. Recommend either reopening a session against that branch or closing the PR.

## What the registry does NOT contain

- PRs created before this hook was installed.
- PRs created via the web UI, `gh api`, or `curl`.
- Commits, reviews, or merge events — only create/edit invocations.
- Body text, labels, or other PR metadata beyond title.

If a question needs that information, fall through to `gh pr view <n>` — don't pretend the registry knows.

## Entry shape

For reference (do not parse by hand — use `query.py`):

```json
{
  "ts": "2026-05-18T18:30:35.843702+00:00",
  "action": "create",
  "pr_number": 9999,
  "session_id": "9271caec-d23a-4981-bfbb-57a92d668ecd",
  "job_id": "9271caec",
  "session_name": "Agent Signature",
  "cwd": "/home/ryan/phoenix",
  "branch": "challenge/foo-bar",
  "repo": "RyanBuehler/phoenix",
  "pr_url": "https://github.com/RyanBuehler/phoenix/pull/9999",
  "title": "feat: add foo"
}
```

`job_id` is null for interactive (non-background) sessions; in that case identify the owner by `session_id`. `session_name` is the friendly label from `~/.claude/jobs/<job_id>/state.json` (the same name shown in `claude agents`) captured at hook time. `query.py` prefers the live name over the cached one when the job is still alive, so renames show up immediately.
