---
name: crucible
description: Use for ANY question or action involving Crucible, sagas, challenges, or bugs — including read-only status queries. Activates on phrases like "saga status", "what is the status of (all) sagas", "what's in review", "what bugs are open", "list sagas", "show challenge X", "create a challenge", "promote saga X", "move challenge to review", "add a comment to challenge Z", or any mention of crucible/saga/challenge/bug. The Crucible CLI is the source of truth — never grep the filesystem or pgrep the server to answer status questions. Teaches CLI binary location, the hyphen-flag convention that makes underscore-style attempts fail, identifier resolution, status vocabulary, list-field append/replace semantics, and the quirks (saga has no status flag, saga create silently drops --challenges, blocked_by uses underscore, server is externally managed).
---

# Crucible CLI — How to Talk to the Project Tracker

Crucible is the project's bespoke saga/challenge/bug tracker. A `crucible` CLI client speaks to a long-running `crucible-server` over local TCP. This skill is what you read before issuing any `crucible ...` command.

## Hard rules

- **The server is managed externally.** Never `start`, `kill`, `probe`, `curl`, `pkill`, or otherwise touch `crucible-server`. If commands fail to connect, report the failure — do not try to start a server.
- **The binary is project-local, not on PATH.** From the engine repo root use `build-crucible-release/bin/crucible`. There is no system-wide `crucible`. Build via `/phoe:build crucible` if the binary is missing.
- **Storage lives at `~/.local/share/crucible-server/`** (`challenges/`, `sagas/`, `bugs/`, `archive/`, `bug-archive/`, `config.json`). Never edit those files by hand — go through the CLI so the server stays consistent.
- **Use the CLI, not raw JSON.** This is reinforced by user feedback: do not hand-author challenge/saga/bug JSON files when a CLI subcommand exists.

## Mental model

Three entity types, each with a parallel command shape:

```
crucible <entity> <subcommand> [<id>|--label=X] [flags ...]
```

Entities: `challenge`, `saga`, `bug`. Plus top-level `init` and `status`.

| Subcommand        | challenge | saga | bug |
|-------------------|:---------:|:----:|:---:|
| create / show / update / delete / list | yes | yes | yes |
| move (status change)                   | yes | NO  | yes |
| list-archive / unarchive               | yes | NO  | yes |
| import / rename                        | yes | yes | yes |
| comment / comments / comment-edit / comment-delete | yes | yes | yes |
| block / unblock                        | yes | NO  | NO  |
| add / remove / reorder / validate (saga<->challenge membership) | NO | yes | NO |

`saga` has **no `move` and no `--status` flag.** A saga's status is rolled up from its constituent challenges. To "promote a saga", move its challenges.

## Flag convention — the #1 gotcha

**All flags are hyphen-cased with `--`:** `--title`, `--label`, `--description`, `--status`, `--priority`, `--severity`, `--reproduction-steps`, `--acceptance-criteria`, `--affected-files`, `--validation-criteria`, `--include-archived`, etc.

The internal Console parameter names visible in `Commands.cpp` are underscore_case (`reproduction_steps`, `affected_files`, `validation_criteria`). **Those are NOT the CLI form.** The client translates `--reproduction-steps=...` into the wire key `reproduction_steps` for you.

Quirky exception: `challenge block` takes `--blocked_by=<id>` (underscore, no hyphen).

If you see `Error: Unknown flag: --foo (did you mean --bar?)`, the suggestion is computed by Levenshtein distance. Trust it.

## Identifying records

Two interchangeable forms accepted by every per-record subcommand:

- Positional integer ID: `crucible challenge show 246`
- Explicit label flag: `crucible challenge show --label=design-discussion-drag-and-drop-across-phoenix`

`saga add`, `saga remove`, `saga reorder` accept either form positionally and parse-int-first: `crucible saga add 42 my-challenge-label` works.

`--label=` (empty value) is indistinguishable from "absent" — supply a real label or use the ID.

## Status vocabulary

`backlog`, `todo`, `in-progress`, `review`, `blocked`, `merged`, `canceled`.

Use `crucible challenge move <id> <status>` to move a challenge column. `unblock` defaults to `todo` if no target status is given.

The `crucible saga list` breakdown columns are abbreviated: **T**=todo, **I**=in-progress, **B**=blocked, **R**=review, **M**=merged.

## Reading state

```
crucible status                       # project name only — not very informative
crucible saga list                    # all sagas with progress breakdown
crucible saga list --oneline          # id<TAB>label, scriptable
crucible saga list --completion       # adds % column (incompatible with --oneline)
crucible saga show <id|--label=X>     # full saga incl. challenge_ids
crucible saga validate <id>           # saga validation criteria + completion

crucible challenge list                                    # active challenges
crucible challenge list --status=todo --priority=high
crucible challenge list --tag=drag-drop                    # filter by single tag
crucible challenge list --no-saga                          # orphans (no saga membership)
crucible challenge list-archive                            # merged/canceled
crucible challenge show <id|--label=X> [--include-archived]

crucible bug list [--status=... --priority=... --severity=... --tag=...]
crucible bug show <id|--label=X>
```

Add `--json` (global flag, before the subcommand) for machine-readable output:

```
crucible --json saga show 44
crucible --json challenge list
```

`--verbose` echoes engine logs. `--port=<N>` overrides the server port (otherwise `CRUCIBLE_SERVER_PORT` env wins).

## Creating

```
crucible challenge create \
  --title="..." \
  --label="kebab-case-label" \
  --description="..." \
  --priority=<low|medium|high|critical> \
  --tags="a|b|c" \
  --acceptance-criteria="line1|line2" \
  --strategy="..." \
  --verification="..." \
  --affected-files="path/a|path/b" \
  --references="..." \
  [--strict-paths]   # error instead of warn on missing affected files

crucible saga create \
  --title="..." \
  --label="..." \
  --description="..." \
  --validation-criteria="line1|line2"
  # NOTE: --challenges=label1|label2 is silently ignored on create.
  # Attach challenges afterwards via `crucible saga add <saga> <challenge>`.

crucible bug create \
  --title="..." \
  --label="..." \
  --description="..." \
  --priority=<low|medium|high|critical> \
  --severity=<minor|moderate|major|crash> \
  --reproduction-steps="step1|step2" \
  --tags="..." \
  --acceptance-criteria="..." \
  --verification="..." \
  --affected-files="..." \
  --references="..."
```

Pipe-separated lists (`a|b|c`) are accepted on create for any list-valued field. The server also accepts `,` as a separator. The CLI emits a deprecation warning on `update` for pipe-separated forms (see below).

## Updating — list fields

`<entity> update` accepts the obvious scalar flags (`--title`, `--description`, `--status`, `--priority`, `--severity`).

**For list fields, the legacy pipe-separated `--tags=a|b|c` form is deprecated on `update`** and emits a warning. Prefer the explicit verbs:

```
--append-<base>=<value>      # repeatable, appends one entry per occurrence
--replace-<base>=<value>     # last occurrence wins, single-entry replacement
--clear-<base>               # empty the list
--<base>-from-json=<path>    # replace from a client-side JSON array file
```

Where `<base>` is one of (note the create-vs-update naming drift):

| Create flag             | Update flag base | Wire key            |
|-------------------------|------------------|---------------------|
| `--tags`                | `tags`           | `tags`              |
| `--acceptance-criteria` | `acceptance`     | `acceptance`        |
| `--strategy`            | `strategy`       | `strategy`          |
| `--verification`        | `verification`   | `verification`      |
| `--affected-files`      | `files`          | `files`             |
| `--references`          | `references`     | `references`        |

So you append a new acceptance criterion with `--append-acceptance="..."`, replace the affected-files list with `--replace-files=path/x` (last `--replace-files=` wins) or `--files-from-json=list.json`.

For sagas, `update` exposes `--append-validation-criteria=` and `--remove-validation-criteria=` directly.

## Saga membership

```
crucible saga add <saga_id|saga_label> <challenge_id|challenge_label>
crucible saga remove <saga> <challenge>
crucible saga reorder <saga> <challenge> <position>
```

To "promote saga X to todo", since saga has no status flag, move its constituent challenges:

```
for id in 342 343 344 ... ; do
  crucible challenge move $id todo
done
```

The saga's rolled-up status updates automatically. Verify with `crucible saga list | grep <label>`.

## Blocking

```
crucible challenge block <id|--label=X> --blocked_by=<other-id> [--reason="..."]
crucible challenge unblock <id|--label=X> [<target-status>]    # default todo
```

`--blocked_by` (underscore!) is the one underscore flag in the surface. `--reason` is hyphen-style.

## Comments

```
crucible <entity> comment <id|--label=X> --body="..." [--author="..."]
crucible <entity> comments <id|--label=X>
crucible <entity> comment-edit <id|--label=X> --index=N --body="..."
crucible <entity> comment-delete <id|--label=X> --index=N
```

Comments are 0-indexed within the record.

## Renaming labels

```
crucible challenge rename <id|--label=X> --to=<new-label>
crucible saga rename <id|--label=X> --to=<new-label>
crucible bug rename <id|--label=X> --to=<new-label>
```

Labels must be kebab-case.

## Archive / unarchive

`merged` and `canceled` records move out of the active list automatically. Browse them with `<entity> list-archive` and restore via `<entity> unarchive <id>` (which moves them back to `todo`).

## Importing JSON

The CLI reads the file client-side (essential when client and server live in different mount namespaces, e.g. sandboxed containers):

```
crucible challenge import <path>          # default: upsert by label
crucible challenge import <path> --create-new   # force new id, suffixed label
crucible saga import <path>
crucible bug import <path>
```

## Discovering flags when unsure

- `crucible --help` — top-level command list.
- `crucible <entity>` (no subcommand) — emits "Missing subcommand. Expected: ..." with the subcommand list.
- `crucible challenge update --help` — full update flag table including the `--append-*` / `--replace-*` / `--clear-*` family.
- Wrong flag → "Unknown flag: --xxx (did you mean --yyy?)" with a Levenshtein suggestion.

If still in doubt, the source of truth is `Applications/Crucible/Source/Private/Crucible.cpp` (CLI dispatch, flag → wire-key translation) and `Applications/Crucible/Source/Private/Commands/Commands.cpp` (server-side parameter declarations).

## Common failure modes

- **`Error: Unknown flag: --status` on `saga update`** — saga has no status flag. Move challenges instead.
- **`Error: Unknown flag: --saga`** on `challenge list` — there is no `--saga` filter. Use `crucible saga show <id>` to enumerate a saga's challenges, or filter list by `--tag` if you tagged consistently.
- **`saga create --challenges=a|b|c` succeeded but saga is empty** — known quirk; `--challenges` is silently dropped on create. Use `crucible saga add` after creation.
- **`Failed to load challenge N: Failed to read file: .../N.json`** — challenge IDs are sparse. The number you tried is unallocated or archived. Use `crucible challenge list` / `list-archive` to find real IDs.
- **`crucible: command not found`** — the binary lives at `build-crucible-release/bin/crucible`, not on PATH. Use the project-relative path or build first via `/phoe:build crucible`.
- **Connection errors** — server is down or wrong port. **Do not start it yourself.** Report the failure to the user.

## Output format reminders

- Default output is human-readable tables with status, priority, label, title columns.
- Use `--json` (before the subcommand) for parseable output, e.g. `crucible --json saga show 44`.
- `crucible saga list` breakdown columns: `T:<todo> I:<in-progress> B:<blocked> R:<review> M:<merged>`.
