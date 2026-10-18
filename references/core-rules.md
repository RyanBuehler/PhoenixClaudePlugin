# Phoenix core rules

These are the phoe plugin's standing conventions for work on the Phoenix engine. The plugin
loads this file into every session and subagent through `hooks/core-rules.py`. Plugin paths
below are under `${CLAUDE_PLUGIN_ROOT}`; `Docs/` paths are in the Phoenix repository.

## Pillars of Phoenix

1. Human and AI users are equal and symbiotic.
2. Creation is play.
3. The Editor bends to the user, never the user to the Editor.
4. Every pixel earns its place.
5. Every action is illuminated.
6. What automation does, the user can undo.

## Where the rules live

| Subject | Authority |
|---|---|
| Code style, naming, comments, design practices — read before writing C++ | `Docs/StyleGuide.md` |
| Idioms, and the antipatterns each replaces | `Docs/Patterns.md` |
| Blessed and banned terms | `Docs/Lexicon.md` |
| Build, test, verify | `/phoe:build`, `/phoe:test`, `/phoe:verify`; `Docs/Forge_DD.md` |
| Smells by ID, with severity | `skills/audit/CHECKS.md`, `skills/ui-design-review/CHECKS.md` |
| Formatter and linter mechanics | `references/tooling.md` |
| C++, Python, Vulkan and portability guides | `references/` |

- `Docs/StyleGuide.md` binds; where this file disagrees with it, this file is stale.
- Keep agent material in this plugin — do not add a `CLAUDE.md`, `AGENTS.md` or other agent guide
  to the repository, because the repository describes the codebase, not how agents work on it.

## Conduct

- Answer at the length the answer needs: cut restatements of the request, options you are not
  taking, and recaps of work the user watched.
- Write plainly — common words, no metaphors, no academic filler. Naming the type, the file and
  the failure is precision, not padding.
- Before a turn's first tool call, say in one sentence what you are about to do, so the user can
  stop you.
- Lead a report with the outcome — what happened, what state the tree or PR is in, what failed —
  then caveats and next steps.
- Search (`git grep`, Glob) before saying the codebase lacks something, and report a miss as
  "I did not find X" — "X does not exist" is a claim a reviewer can falsify.
- Before acting on a review comment that names a construct (a cast, RTTI, exceptions, a macro, a
  module keyword), confirm it is on or near the cited line; if it is not, ask the reviewer what
  they meant — line numbers drift across PR updates.
- Give every Bash call absolute paths, or a `cd` in the same call — a subagent's shell resets its
  directory, and a worktree and the main checkout are separate trees.
- Ask before each instance of machine load — CPU spinners, `stress`, memory balloons, disk
  fillers, fork storms, `-j` above the core count — because the host is shared with the user and
  other agents, and orphaned load is blamed on whoever runs next.
  `references/machine-load.md` has the self-limiting form and how to read a starved host.
- Keep AI attribution out of commits, PRs, comments and tags — no `Co-Authored-By` trailer, no
  "Generated with" banner.

## Branches and worktrees

- Work on a `<type>/<label>` branch in its own worktree, created from the main repo root:
  `git worktree add .claude/worktrees/<type>-<label> -b <type>/<label>`. Types are `challenge`,
  `bug`, `doc`, `ci` and `misc`; prefix the label with the affected system when it helps
  reviewers (`bug/windows-liaison-fix-focus`).
- Keep the whole branch name lowercase kebab-case within 40 characters — Forge on Windows is not
  long-path aware. `hooks/branch-worktree-check.py` enforces this and names the shortened branch
  label for a long Crucible label; the full Crucible label still goes in `--label=` and the PR
  body's `Crucible:` line.
- After pushing, remove only the worktree. Once the PR provably lands, delete the worktree, the
  local branch and the remote branch per `references/concluding-work.md`.

## Searching

- Search with `git grep` — it sees only your worktree's tracked files, while a root-wide
  `grep -r` or `find` also sweeps `.forge*/`, `.bootstrap-out/` and `.claude/worktrees/`.
- Confirm an absence with a second form — `git grep` exits 0 both on no match and on a pathspec
  that matched nothing.
- Under zsh (Linux hosts), quote every glob-bearing flag and a bare `===`, and pass a pattern
  containing `>` with `-e` — an unmatched glob aborts the line and reads as a search miss.

## Build, verify, push

- Build, test, lint and format only through Forge (`/phoe:build`, `/phoe:test`, `/phoe:lint`,
  `/phoe:format`) — the repository's forbidden-token audit fails any external generator.
- Do not build or test after every change. `/phoe:verify` is required before a PR opens; one
  verify may cover several commits, such as a stack's layers. This overrides TDD and
  verification-before-completion guidance from other skills.
- Name the profiles you verified whenever you report verification.
- Treat `forge clean` and `forge build --clean` as destructive. If Forge refuses or asks, stop and
  ask the user, and never add `--force` yourself, because the build tree holds files Forge did not
  produce, such as saved Editor projects, and `--force` deletes them permanently.
- Push and open PRs without asking; `hooks/push-gate.py` checks git identity and credentials first.
- Add tool permissions to `~/.claude/settings.json`, not `.claude/settings.local.json`, so they
  apply in every checkout and worktree.

## Codebase rules

Rules the repository docs do not state, or state as a pattern summarized here.

- Write American English in code and comments (color, center, behavior); fix your own lines, do
  not churn existing text.
- Guard non-finite values with `Math::IsFinite`, not `std::isfinite` — it constant-evaluates, and
  the curated `Std` carries no `<cmath>` on the clang arm.
- Test pointers and handles directly (`if (!Current)`, `REQUIRES(Found, ...)`), not against
  `nullptr`.
- Write acronyms all-caps in module and type names (`GLTF`, not `Gltf`); `Json` is the one
  exception.
- Name a new concept by `Docs/StyleGuide.md` §Naming a new symbol, and never drive a rename with
  a bulk regex. Keep working with your best name; confirm production names (not trial-only ones)
  with Ryan before the work ships.
- One owner drives each system through its concrete interface; all other code reaches it through
  a registry-discovered subsystem that names no concrete type (`Docs/Patterns.md` §Ownership
  Tiers). A system without a clear owner gets a designated one or is Tier-2-only.
- Foreign TUs name only their own value types. Across an open type set, erase the value (bytes
  plus a per-type op) and let the owner resolve storage: `byte*` behind a typed accessor, never
  `void*` in a public signature (§Value-Erasure Boundary).
- Submit intent, don't register objects: hand the owner a self-contained description of the work
  and read back a result (§Submitted Request). Never pass yourself to a system so it can call back
  or "make you ready"; pass values, not closures over foreign mutable state, and prefer a per-tick
  snapshot the owner consumes.
- Every Editor operation is one Symbiote binding; Python, the console, the agent action and user
  controls are projections of it, and compositions are Python, never new bindings. Change a
  `Docs/Symbiote_DD.md` §0 rule only with Ryan — it changes the pillar.
- Use no third-party libraries; OS dependencies (X11, ALSA, Vulkan) are the only exception.
- Carry build configuration in `Build::` module constants, never `-D` macros.
- Refactor freely — the software is unreleased, so add no back-compat shims or deprecation paths.
- Linux builds use Clang. Import specific `Phoenix.<Module>` partitions; there is no
  `import Phoenix;` umbrella.
- Keep the Editor UI native (Mosaic) — no HTML, JS, CSS or HTTP surface.
- Keep trial content out of production source: trials live in the owning module's `Trials/`, and
  `Source/` carries no trial scaffolding, fixtures, or comments describing a trial's setup.
