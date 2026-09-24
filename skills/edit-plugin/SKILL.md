---
name: edit-plugin
description: Edit the PhoenixClaudePlugin source — add or modify skills, agents, hooks, or references following plugin conventions, then bump the calendar version.
allowed-tools: Read, Edit, Write, Bash, Glob, Grep, Agent
disable-model-invocation: true
---

Edit the PhoenixClaudePlugin (the "phoe" plugin for Claude Code).

## Arguments

- **`<path>`** — *(optional)* path to the plugin source repository (default: `~/phoenixclaudeplugin`)

## 1. Locate the Plugin Repo

If a path argument was provided, use it. Otherwise, ask the user. The default location is `~/phoenixclaudeplugin`.

Verify the path exists and contains `.claude-plugin/plugin.json` with `"name": "phoe"`.

## 2. Make Requested Edits

The user will describe what changes to make (new agents, skills, CLAUDE.md updates, reference docs, hooks, etc.). Apply those changes following the plugin's existing conventions:

- **Skills**: `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). Slash workflows
  are skills too — there is no `commands/` directory. A workflow only the user starts
  (`/phoe:plan`, `/phoe:execute`) sets `disable-model-invocation: true`, which drops it from
  the model's listing entirely.
- **Agents**: Markdown files in `agents/` with YAML frontmatter (`name`, `description`, `tools` fields)
- **Descriptions are paid every session.** Every skill and agent `description` sits in the
  system prompt of every session. Keep an agent's to one sentence (~150 chars) naming what it
  covers; keep a skill's to when it applies. Trigger phrases, "not for X, use Y" routing, and
  other detail go in the body, which loads only on invocation.
- **Hooks**: Update `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}` for script paths
- **References**: Markdown files in `references/`
- **Scripts**: Python files in `scripts/`, invoked from a skill as
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py`. Anything a skill must do
  deterministically — classification, destructive actions — belongs here rather than
  in the skill's prose, and gets a `tests/test_<name>.py` alongside it.
- **CLAUDE.md**: The plugin's project-level instruction file at the repo root

Review existing files for style and formatting conventions before writing new ones.

## 3. Bump the Version

Read the current version from `.claude-plugin/marketplace.json`. Version lives there only — `plugin.json` does not carry a version field.

The project uses calendar versioning: `YYYY.MINOR.PATCH` (e.g., `2026.0.0`). Default to a **patch** bump (`YYYY.MINOR.PATCH+1`) — do not change the year or minor segments. Confirm with the user before bumping minor or year (e.g., for a major new feature or the first release of a new calendar year). Apply the bump only to `.claude-plugin/marketplace.json`.

## 4. Report

Tell the user what was changed and the new version number. Do NOT commit or push — leave that to the user.
