---
name: edit-plugin
description: Edit the PhoenixClaudePlugin source — add or modify skills, agents, hooks, or references following plugin conventions, then bump the calendar version.
allowed-tools: Read, Edit, Write, Bash, Glob, Grep, Agent
disable-model-invocation: true
---

Edit the PhoenixClaudePlugin (the "phoe" plugin for Claude Code).

## Arguments

- **`<path>`** — *(optional)* path to the plugin source repository (default: `~/Agents/PhoenixClaudePlugin`)

## 1. Locate the Plugin Repo

If a path argument was provided, use it. Otherwise, ask the user. The default location is `~/Agents/PhoenixClaudePlugin`.

Verify the path exists and contains `.claude-plugin/plugin.json` with `"name": "phoe"`.

## 2. Make Requested Edits

The user will describe what changes to make (new agents, skills, core-rule updates, reference docs, hooks, etc.). Apply those changes following the plugin's existing conventions:

- **Skills**: `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). Slash workflows
  are skills too — there is no `commands/` directory. A workflow only the user starts
  (`/phoe:plan`, `/phoe:execute`) sets `disable-model-invocation: true`, which drops it from
  the model's listing entirely.
- **Agents**: Markdown files in `agents/` with YAML frontmatter (`name`, `description`, `tools` fields)
- **Descriptions are paid every session.** Every skill and agent `description` sits in the
  system prompt of every session. Keep an agent's to one sentence (~150 chars) naming what it
  covers; keep a skill's to when it applies. Trigger phrases, "not for X, use Y" routing, and
  other detail go in the body, which loads only on invocation.
- **Hooks**: Update `hooks/hooks.json`, quoting the placeholder in every command
  (`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`) so a path with spaces stays one argument.
  A rule a hook enforces does not also need prose.
- **References**: Markdown files in `references/`
- **Core rules**: `references/core-rules.md` is the plugin's always-on context.
  `hooks/core-rules.py` returns it on every SessionStart and SubagentStart, because a `CLAUDE.md`
  at a plugin root is never loaded. Keep it under the hooks' 10,000-character context limit
  (`tests/test_core_rules.py` checks this) and to rules every session needs; anything used by one
  workflow goes in that skill or a reference. Write each rule as "do X — because Y" in one clause.
- **Check catalogs**: a review skill keeps its smells in a `CHECKS.md` beside its `SKILL.md`, as
  `skills/audit/` and `skills/ui-design-review/` do. A catalog holds no rules of its own: each check
  is a smell, the section that owns the rule, a severity, and what an agent may do about it.
- **Scripts**: Python files in `scripts/`, invoked from a skill as
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py`. Anything a skill must do
  deterministically — classification, destructive actions — belongs here rather than
  in the skill's prose, and gets a `tests/test_<name>.py` alongside it.

Review existing files for style and formatting conventions before writing new ones. Then run
`python3 -m unittest discover -s tests` and `claude plugin validate .` from the plugin root.

## 3. Bump the Version

Read the current version from `.claude-plugin/marketplace.json`. Version lives there only — `plugin.json` does not carry a version field.

The project uses calendar versioning: `YYYY.MINOR.PATCH` (e.g., `2026.0.0`). Default to a **patch** bump (`YYYY.MINOR.PATCH+1`) — do not change the year or minor segments. Confirm with the user before bumping minor or year (e.g., for a major new feature or the first release of a new calendar year). Apply the bump only to `.claude-plugin/marketplace.json`.

## 4. Commit and push

Commit on the plugin repo's `main` and push. The plugin is the one repo that takes direct commits
to `main`; Phoenix changes always go through a PR. If the push is rejected, rebase the unpushed
commit onto `origin/main` and push again.

## 5. Report

Tell the user what changed, the new version and the commit.
