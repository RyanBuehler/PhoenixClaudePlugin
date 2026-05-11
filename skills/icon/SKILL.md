---
name: icon
description: Use when adding, replacing, or auditing Phosphor icons in the Phoenix Editor. Activates on phrases like "add a save icon", "find a Phosphor icon for X", "vendor a new icon", "swap the X icon for Y", "what icon should I use for Z", "/phoe:icon save", or any direct interaction with Applications/Editor/Content/Icons/.
---

# /phoe:icon — Vend a Phosphor icon into the Editor

This skill adds or replaces a Phosphor icon end-to-end: search the catalog, pick a name, fetch all five non-duotone weights, place them in the engine tree, and print a usage snippet. It is conversational — you (the model) execute the steps below; there is no compiled binary.

## Hard rules

- **Phosphor only.** Other icon families (Lucide, Feather, Material) are intentionally not supported. A new family means a new sibling directory under `Applications/Editor/Content/Icons/` with its own LICENSE — propose that as a separate change, not via this skill.
- **All five non-duotone weights.** Every vendored icon ships in `regular`, `light`, `bold`, `thin`, and `fill`. Duotone is out of scope: the Editor's R8 SDF atlas cannot represent two-opacity paths.
- **Refuse to overwrite without `--force`.** If the destination filename already exists in any of the five weight directories, stop and ask. Stale icons stay until explicitly replaced.
- **Bump the plugin version on a change to this skill** (PATCH bump in `PhoenixClaudePlugin/.claude-plugin/marketplace.json`). Vendoring icons does NOT require a plugin version bump — the version tracks the skill itself, not its uses.
- **Never edit the SVG content.** The vendored file is byte-for-byte what Phosphor publishes. The parser handles arcs and curves; do not pre-process.
- **Refuse if the engine repo has uncommitted changes**, unless the user explicitly asks to vendor on top of in-progress work. The vendoring step touches the engine tree; staging a clean baseline first prevents unrelated diff noise.

## Mental model

Phosphor publishes its icons as SVGs at GitHub:

```
https://raw.githubusercontent.com/phosphor-icons/core/main/assets/<weight>/<filename>
```

The catalog (icon names + aliases + tags + categories) lives at:

```
https://raw.githubusercontent.com/phosphor-icons/core/main/src/icons.ts
```

The Editor's vendored tree mirrors Phosphor's directory structure:

```
Applications/Editor/Content/Icons/
  phosphor/
    LICENSE              MIT, verbatim from upstream
    regular/<name>.svg
    light/<name>-light.svg
    bold/<name>-bold.svg
    thin/<name>-thin.svg
    fill/<name>-fill.svg
```

Runtime: `IconRegistry::GetIcon("<name>")` returns an `optional<IconHandle>`. The Editor builds the registry from `Content/Icons/phosphor/regular/` at startup; other weights are not loaded at runtime today (the registry only reads the `regular/` directory). Vendoring all five weights still matters because it preserves the option to switch the registry's default weight without a re-fetch.

## Naming convention

Phosphor's filenames are preserved exactly as upstream:

- Regular weight: `<name>.svg` — for example, `floppy-disk.svg`
- Other weights: `<name>-<weight>.svg` — for example, `floppy-disk-bold.svg`, `arrow-left-thin.svg`

Names are kebab-case. The same `<name>` appears in every weight directory; only the suffix differs. The runtime registry keys icons by `<name>` plus a weight enum, never by filename.

## Default weight: regular

`regular` is Phosphor's design baseline — every other weight is a variant of it. Choosing regular as the runtime default keeps consumer call sites short (`GetIcon("floppy-disk")` rather than `GetIcon("floppy-disk", IconWeight::Regular)`) and matches Phosphor's own documentation. The other four weights ship for parity with Phosphor's official packaging and so a future change to the registry's default weight does not need a re-fetch.

## Skill flows

There are three flows. Pick by user intent:

1. **Search** — "find me an icon for X" / "what's a good Phosphor icon for Y" → run [Search](#search) only, present top 5, stop. The user picks; the next turn runs Vendor.
2. **Vendor** — "add a `<name>` icon" / "vendor floppy-disk" / "/phoe:icon floppy-disk" → run [Vendor](#vendor) end-to-end on the supplied name.
3. **Search-then-vendor** — "/phoe:icon save" (a query, not a known name) → run [Search](#search), pick the highest-scoring match if it's clearly dominant; otherwise present top 5 and ask.

If the argument exactly matches a known catalog name (e.g. `/phoe:icon floppy-disk`), skip search and go straight to Vendor.

## Catalog cache

Cache the parsed catalog at `~/.cache/phoenix/phosphor-icons.json`. Refresh if the file is missing or older than 7 days.

To refresh:

1. `mkdir -p ~/.cache/phoenix`
2. `curl -sSfo ~/.cache/phoenix/phosphor-icons.ts https://raw.githubusercontent.com/phosphor-icons/core/main/src/icons.ts`
3. Parse the TypeScript-syntax source into JSON. The format is mechanically generated, so a regex over the per-icon blocks suffices. Each entry looks like:

   ```ts
   {
     name: "floppy-disk",
     pascal_name: "FloppyDisk",
     alias: { name: "save", pascal_name: "Save" },        // optional
     categories: [IconCategory.OFFICE, IconCategory.SYSTEM],
     figma_category: FigmaCategory.OFFICE,
     tags: ["save", "store", "data"],
     codepoint: 59904,
     published_in: 1.0,
     updated_in: 1.0,
   },
   ```

   Parse fields: `name`, `pascal_name`, `alias.name` (if present), `categories` (strip the `IconCategory.` prefix and lowercase), `tags` (strip leading `*new*` and `*deprecated*` markers but keep them as a separate `flags` field), `published_in`, `updated_in`.

4. Write `~/.cache/phoenix/phosphor-icons.json` as an array of those parsed entries. The `.ts` file can be deleted after parsing — keep only the JSON.

5. The catalog has roughly 1,500 entries. The JSON file is small enough (<1 MB) to load into memory in one shot.

If the user asks for a "fresh" pull (e.g. they suspect an icon was just added), bypass the staleness check and refresh unconditionally.

## Search

Score each catalog entry against the user's query. Lowercase both sides.

```
score(entry, query) =
    (10 if query == entry.name)                                // exact-name match
  + (8  if query == entry.alias.name)                          // exact-alias match
  + (5  if query is a token in entry.name.split('-'))          // name-token match
  + (3  if query is a substring of entry.name)                 // name-substring match
  + (3  if query is one of entry.tags)                         // tag exact match
  + (2  if query is a substring of any tag)                    // tag substring
  + (1  if query is one of entry.categories)                   // category exact
  + (1  if query is a substring of any category)               // category substring
```

Multi-word queries: split on whitespace, score each word separately, sum. Words that match nothing contribute zero (no penalty).

Return the top 5 by score, descending. Tie-break by `name` ascending (alphabetical). If the top hit's score is at least double the second, treat it as dominant and proceed without asking.

**Floppy-disk smoke test.** Querying `save` must return `floppy-disk` in the top 5 — Phosphor uses `save` as a tag on `floppy-disk` and as the icon's alias. If your search doesn't surface it, the parsing is broken; verify the alias and tag fields landed in the cache.

Display search results to the user as one line per icon:

```
floppy-disk      tags: save, store, data        categories: office, system
floppy-disk-back tags: save-as, version, return categories: office, system
...
```

Plus a one-line note: "Top hit dominant — proceeding to vendor floppy-disk." OR "Pick one and re-run /phoe:icon <name>."

## Vendor

Given a confirmed icon name (e.g. `floppy-disk`):

1. **Confirm engine repo path.** The user's working directory (or the engine repo root, if discoverable via `git rev-parse --show-toplevel`) should contain `Applications/Editor/Content/Icons/phosphor/`. If not, stop with a clear error.

2. **Refuse if any target file already exists** (across all five weights), unless `--force` is set. Print the colliding paths and ask the user to confirm or rename.

3. **Fetch all five weights.** For each `<weight>` in `regular, light, bold, thin, fill`:

   - URL: `https://raw.githubusercontent.com/phosphor-icons/core/main/assets/<weight>/<filename>`
     where `<filename>` is `<name>.svg` for regular, `<name>-<weight>.svg` for the rest.
   - Destination: `Applications/Editor/Content/Icons/phosphor/<weight>/<filename>`
   - Use `curl -sSfo <dest> <url>`. The `-f` flag fails on HTTP 404, which is the common
     mode when an icon doesn't exist in a given weight. If any weight 404s, abort the entire
     vendoring (delete the partial files) and report which weight is missing — do not ship a
     partial set.

4. **Print the usage snippet.** Once vendored, surface what the consumer code needs:

   ```cpp
   // In a panel constructor (after Editor::UI threads its IconRegistry in):
   if (m_IconRegistry)
   {
       if (auto Handle = m_IconRegistry->GetIcon("<name>"))
       {
           m_MyIcon->SetHandle(*Handle);
       }
   }
   ```

   Plus a reminder of the IconImage tessera shape:

   ```cpp
   shared_ptr<IconImage> Icon = make_shared<IconImage>();
   Icon->SetHandle(Handle);
   Icon->SetTint(Color::RGBA{ 1.0f, 1.0f, 1.0f, 1.0f });
   Icon->SetSize(UISize::Pixels(16, 16));
   Parent->AddChild(Icon);
   ```

   If the consumer is a layout file (JSON), point at the `IconImage` tessera type that's
   registered in `Engine/Modules/Rendering/Mosaic/Source/Private/Layout/TesseraFactory.cpp`.

5. **Do not rebuild the editor.** The IconRegistry rebuilds its atlas on next launch — the
   user re-runs `/phoe:build engine` (or just relaunches) when they want the icon visible.
   If the user explicitly asks for a build, defer to `/phoe:build`.

## Manual-add fallback

If the skill is unavailable (e.g. the user is on a different machine or wants to vendor offline), the steps reduce to:

1. Pick a name from https://phosphoricons.com — for example, `floppy-disk`.
2. Download all five non-duotone weights from the URL pattern above. Save each into the matching weight directory under `Applications/Editor/Content/Icons/phosphor/`.
3. Rebuild the Editor; the IconRegistry rebuilds the atlas on next startup.

The manual flow skips the catalog cache and the search heuristic but produces the same on-disk result.

## Conventions

- Names are kebab-case, exactly as Phosphor publishes them. Do not pascal-case, snake-case,
  or otherwise transform. The runtime registry keys on the kebab-case name.
- Filename suffix matches the weight directory: `regular/<name>.svg`, `light/<name>-light.svg`,
  etc. Don't strip the suffix or rename to a single canonical form — Phosphor's tooling
  expects this layout.
- The `/phoe:icon` skill is the sanctioned entry point for adding a Phosphor icon.
  Hand-vendoring works (see [Manual-add fallback](#manual-add-fallback)) but skips the
  search-and-confirm step; prefer this skill.

## Quirks

- **Phosphor's `*new*` and `*deprecated*` tag markers** are not real semantic tags — they
  are flags that the catalog uses for changelog filtering. Strip them out of the search
  scoring (treat them as no-op tokens) but preserve them in the parsed cache so a future
  flow can show "this icon was added in 2.1" if useful.
- **Some icons have aliases that point to other icons** — for example, `save` is an alias
  on `floppy-disk`. The alias is a canonical synonym, not a separate icon; it does NOT
  exist as `assets/regular/save.svg`. Never try to fetch a URL based on an alias name.
- **Phosphor SVGs use `A` (arc) commands.** The Editor's SVG parser handles arcs (added
  alongside the initial vendoring), but do not assume future Phosphor releases keep the
  same path-data shape. If a freshly fetched icon fails to load at runtime, dig into
  `Engine/Modules/Rendering/Montage/Source/Private/SVGPathParser.cpp` rather than blaming the
  vendoring.
- **viewBox is consistently `0 0 256 256`** across all current Phosphor weights, but the
  parser does not assume this — it reads the actual attribute. If a Phosphor release ever
  changes the viewBox, vendored icons will simply scale differently in the atlas; no code
  change required.

## Don'ts

- Do NOT modify SVG content for any reason.
- Do NOT cache fetched SVGs anywhere except the engine tree (no `~/.cache/phoenix/svg/`).
- Do NOT add files to weight directories that don't have all five matching siblings — the
  per-weight count must stay equal.
- Do NOT bump the plugin version unless this skill itself changed (this is the plugin's
  general version-bump rule; vendoring icons is engine-side work).

## When to stop and ask

- The query has no clear top hit (top score < 2× second).
- The destination already exists and `--force` was not provided.
- A weight 404s during fetch (do not ship a partial set without explicit confirmation).
- The engine repo has uncommitted changes and the user did not say "on top of WIP".
