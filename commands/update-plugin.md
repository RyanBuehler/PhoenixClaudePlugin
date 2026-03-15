---
description: Update the PhoenixClaudePlugin from its source repository. Takes an optional path argument to the plugin repo, otherwise asks. Applies changes and bumps the version number.
allowed_tools: Read, Edit, Write, Bash, Glob, Grep, Agent
---

# Update PhoenixClaudePlugin

You are updating the PhoenixClaudePlugin (the "phoe" plugin for Claude Code).

## Step 1: Locate the plugin repo

The user may provide the path to the plugin source repository as an argument. If not provided, ask for it. The default location is `~/Agents/PhoenixClaudePlugin`.

Verify the path exists and contains `.claude-plugin/plugin.json` with `"name": "phoe"`.

## Step 2: Make requested edits

The user will describe what changes to make (new agents, commands, CLAUDE.md updates, reference docs, hooks, etc.). Apply those changes following the plugin's existing conventions:

- **Commands**: Markdown files in `commands/` with YAML frontmatter (`description` field)
- **Agents**: Markdown files in `agents/` with YAML frontmatter (`name`, `description`, `tools` fields)
- **Hooks**: Update `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}` for script paths
- **References**: Markdown files in `references/`
- **CLAUDE.md**: The plugin's project-level instruction file at the repo root

Review existing files for style and formatting conventions before writing new ones.

## Step 3: Bump the version

Read the current version from `.claude-plugin/plugin.json`.

Present the current version and ask the user whether this is a:
- **Patch** (bug fixes, minor wording changes) — bump `x.y.Z`
- **Minor** (new features, new agents/commands, non-breaking changes) — bump `x.Y.0`
- **Major** (breaking changes, significant restructuring) — bump `X.0.0`

If the change is clearly a patch or minor update, suggest the appropriate level but still confirm. Apply the chosen version bump to `.claude-plugin/plugin.json`.

## Step 4: Summary

Report what was changed and the new version number. Do NOT commit or push — leave that to the user.
