---
name: crucible
description: Use for ANY question or action involving Crucible, sagas, challenges, or bugs — including read-only status queries. Activates on phrases like "saga status", "what's in review", "create a challenge", "move challenge to review", or any mention of crucible/saga/challenge/bug.
---

# Crucible CLI — How to Talk to the Project Tracker

Crucible is the project's bespoke saga/challenge/bug tracker. A `crucible` CLI client speaks to a long-running `crucible-server` over local TCP. This skill is what you read before issuing any `crucible ...` command.

## Hard rules

- **The server is managed externally.** Never `start`, `kill`, `probe`, `curl`, `pkill`, or otherwise touch `crucible-server`. If commands fail to connect, report the failure — do not try to start a server.
- **The binary is project-local, not on PATH.** Forge builds it under a per-profile subtree whose name varies by host/build, so don't hardcode it. **Search the configured build tree (`.forge/`) as well as the bootstrap output (`.forge-out/`), newest first** — `.forge-out/` can hold a months-stale copy that still reports a plausible version number, and picking it up costs a round trip on every fresh session:

  ```bash
  CRUCIBLE=$(find Applications/Forge/.forge Applications/Forge/.forge-out \
      -type f -path '*/bin/crucible' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -1 | cut -d' ' -f2-)
  ```

  Then call `"$CRUCIBLE" ...`. There is no system-wide `crucible`. Build via `/phoe:build crucible` if the binary is missing.
- **Storage lives at `~/.local/share/crucible-server/`** (`challenges/`, `sagas/`, `bugs/`, `archive/`, `bug-archive/`, `config.json`). Never edit those files by hand — go through the CLI so the server stays consistent.
- **Use the CLI, not raw JSON.** This is reinforced by user feedback: do not hand-author challenge/saga/bug JSON files when a CLI subcommand exists.
- **The CLI is the source of truth for status.** Never grep the filesystem or pgrep the server to answer status questions — ask the CLI.

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

`backlog`, `todo`, `active`, `review`, `blocked`, `merged`, `canceled`. (There is **no `in-progress`** — the CLI rejects it; use `active`.)

Use `crucible challenge move <id> <status>` to move a challenge column. `unblock` defaults to `todo` if no target status is given.

The `crucible saga list` breakdown columns are abbreviated: **T**=todo, **A**=active, **B**=blocked, **R**=review, **M**=merged, **C**=canceled. "Done" counts **M+C**.

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

## Status report — the default "saga status" output

When the user asks for "saga status", a "status table", "where are we", or similar, **reconcile first, then print the report below.** This is the canonical format; don't invent ad-hoc tables.

**1. Reconcile in-flight work** (so the board is true, not just what the tracker last recorded):
- `git fetch origin -q`. For each `review`/`merged` challenge, confirm its PR merge-commit is an ancestor of `origin/main` — `git merge-base --is-ancestor <oid> origin/main` — before trusting it. A squash-merge can show MERGED yet never reach main. Move a verified stale `review` → `merged`; leave it in `review` if its PR is still open.
- For each `blocked` challenge, if its `blocked_by` target is now merged, `unblock` it — **but** if it's a capstone with more unmet prerequisites, re-point the block to the next one (`challenge block <id> --blocked_by=<next>`); a capstone isn't pickable until all prereqs land.
- **Lift redundant same-saga in-order blocks.** A challenge blocked only on its immediate/earlier predecessor within the *same* saga, in natural order, is a redundant block — the saga ordering already conveys the sequence. `unblock` it to `todo`, keeping only genuine cross-saga or out-of-order blocks (see "When to block — and when NOT to" under **Blocking**). Treat these the same as stale/satisfied blocks.
- Briefly list every move you made (old → new + why) above the report.

**2. Pull data:** `crucible saga list --completion`, `crucible challenge list --no-saga`, `crucible bug list`.

**3. Print these sections, in order:**

1. **▶ In-flight & blocked sagas** — markdown table, one row per saga with status `active`/`blocked`/`todo` (omit `complete` and `backlog`). Columns: `# | Saga | Done | Progress | Remaining`. Progress = a 10-cell bar `▰`(done=M+C) / `▱`(rest) inline-code-wrapped + `%`. Remaining in words (`1 blocked, 4 todo`), never glyph soup. Suffix blocked sagas with ⛔.
2. **◆ Sagaless challenges** — orphans from `--no-saga` (non-terminal only): `# | status | priority | label`.
3. **🐞 Bugs** — open bugs: `# | severity | priority | label`. If all merged/none, write "none open".
4. **· Backlog** — two groups: **Parked** (has challenges, set aside) and **Shell sagas** (0 challenges → need `/phoe:plan <label>` to decompose into challenges). One `#id label` per entry.
5. **✓ Complete** — collapse to a single line: count + ids. Never one row per saga.
6. **Totals** — `N sagas · done/total challenges (P%)` + a 20-cell bar.
7. **⚠ Synopsis & dependency chains** — prose, the payoff section. For each blocked saga/challenge give the chain (`#314 → #313 → #356–#359`), what would unblock it, and special considerations: capstones not yet pickable, `review` items with *open* vs *merged* PRs, squash-merge retarget hazards, parked-vs-shell distinction. Close with the single most useful next action.

Parse the `--completion` rows with `^(\d+)\s+(\S+)\s+T:(\d+)\s+A:(\d+)\s+B:(\d+)\s+R:(\d+)\s+M:(\d+)\s+C:(\d+)\s+(\d+)/(\d+)\s+(\S+)\s+(.*)$`. Keep bars in inline code so columns align.

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

**`Warning: affected_files path does not exist` is unreliable — ignore it, and check the paths
yourself.** The existence check runs against the *server's* notion of the project root, not the
directory the command was run from, so paths that plainly exist in the repo root are warned about
anyway (`--affected-files="CLAUDE.md"` from the repo root warns). Treating the warning as
load-bearing trains you to ignore a check that should be. Verify paths with `ls`/`git ls-files`
before creating, and don't use `--strict-paths` — it turns these false warnings into hard errors.

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

**The `--append-*` / `--replace-*` / `--clear-*` family is a *challenge* feature. `bug update` does
not have it.** A bug's list fields (`--tags`, `--acceptance-criteria`, `--verification`,
`--affected-files`, `--references`) accept only the pipe-separated whole-list form, which **replaces**
the list — to add one tag you must restate every tag. Reaching for the challenge form fails with
`Error: Unknown flag: --append-tags`, which reads like a typo rather than an entity difference. Read
the current list off `bug show` first, then send the full replacement:

```bash
crucible bug update <id> --tags="existing1|existing2|new"
```

(`--review-link` / `--replace-review-link` / `--clear-review-link` *are* available on bugs — that
one is a scalar, not a list.)

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

**`challenge move <id> blocked` is refused** — it errors with *"not supported because it requires
`--blocked_by`"* and points you at `challenge block`. There is no reason-only block, so a challenge
blocked by newly discovered work has nothing to point at yet: **file the blocker challenge first**,
then `challenge block <id> --blocked_by=<new-id>`. (Bugs are different — `bug move <id> blocked`
works, because bugs have no `block`/`unblock` subcommands at all.)

### When to block — and when NOT to

A challenge's **position in its saga's ordered challenge list already encodes linear sequence.** Do NOT `block` a challenge merely because it comes after another in the *same* saga — the ordering conveys "do these in turn." An explicit block is warranted only when there is a genuine dependency *and* a **deviation** from the normal in-order same-saga chain. Two deviation cases:

1. **Cross-saga blocker** — the challenge depends on a challenge in a *different* saga (e.g. #312 in saga B can't start until #290 in saga A merges).
2. **Out-of-order intra-saga dependency** — within one saga, a challenge depends on one that comes *later* in the order, or a re-order / insertion left the dependency no longer expressed by natural sequence (e.g. #350 depends on #356, which sits after it).

In every other case — challenge N depending on its immediate or earlier predecessor in the same saga, in natural order — do NOT block. Reserve `blocked` status for real deviations.

## Comments

```
crucible <entity> comment <id|--label=X> --body="..." [--author="..."]
crucible <entity> comments <id|--label=X>
crucible <entity> comment-edit <id|--label=X> --index=N --body="..."
crucible <entity> comment-delete <id|--label=X> --index=N
```

**`--index=N` is 1-based, and `N` is a stable comment ID — not a position.** The first comment is
`#1`. Deletes never renumber the survivors, so the numbering goes non-contiguous: delete `#1` of
three and the rest stay `#2`/`#3`, and the next comment added becomes `#4`. **Read the index off
`<entity> comments`** — never count it from the listing's order, and never count from zero.

An out-of-range index is rejected (`Error: Comment index N not found`), but a wrong-but-existing
index silently succeeds and reports `Comment #N updated`. So an off-by-one does not error — it
overwrites a real comment, and `comment-delete` destroys one outright. There is no comment history
and no undo.

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
crucible challenge import <path>          # upsert by label — but see the caveat below
crucible challenge import <path> --create-new   # force new id, suffixed label
crucible saga import <path>
crucible bug import <path>
```

**The upsert only matches *active* records, and it fails silently.** `import --help` promises
update-in-place when a record with the file's label exists — but the lookup skips the archive, so a
label that lives only in `list-archive` (anything `merged` or `canceled`) does not match. Import then
takes the create path: a **new id, a suffixed label, and no warning**. Following the documented
upsert during one consolidation produced a duplicate that had to be deleted by hand.

A silent duplicate is worse than a rejection, so check before you import and after:

```bash
crucible <entity> show --label=<LABEL> --include-archived   # does it already exist, archived or not?
crucible <entity> list | grep <LABEL>                       # exactly one afterwards?
```

If the record is archived, `unarchive` it first and then import, rather than importing on top of it.

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
- **`crucible: command not found`** — the binary is not on PATH. Discover it with the newest-first search in **Hard rules** above, which covers both `.forge/` and `.forge-out/`; or build it via `/phoe:build crucible`.
- **`bug list --tag=<X>` returns every bug** — the tag filter is silently ignored on bugs (a nonsense tag returns the full list too, while `--status`/`--priority`/`--severity` do filter). Do not read the unfiltered result as "every bug carries this tag". Filter client-side instead: `crucible --json bug list > bugs.json`, then select on `tags` — and redirect it, the JSON runs to ~145 KB for a few dozen bugs.
- **`Error: Unknown flag: --append-tags` on `bug update`** — the incremental list verbs are challenge-only. Restate the whole list with the pipe-separated form.
- **A second record appears after `import`** — the upsert missed an archived label. See **Importing JSON**.
- **Connection errors** — server is down or wrong port. **Do not start it yourself.** Report the failure to the user.

## Output format reminders

- Default output is human-readable tables with status, priority, label, title columns.
- Use `--json` (before the subcommand) for parseable output, e.g. `crucible --json saga show 44`.
- `crucible saga list` breakdown columns: `T:<todo> A:<active> B:<blocked> R:<review> M:<merged> C:<canceled>`.
