# Targeted compilation from a profile database

This is an early syntax/type check of one ordinary Clang translation unit. It does not link,
run trials, check imported implementation behavior, or replace the required Forge build/test/verify.

## Prerequisites and provenance

Use the worktree's own bootstrapped Forge and intended profile. Read `Docs/Forge_DD.md` §3.1:
`compile_commands.json`, response files and module artifacts are shared, although graphs are
per-profile. A warm directory or a matching TU entry does not establish which profile wrote it.

Before checking, establish exclusive access by coordinating with every writer of that tree.
Record the worktree commit/diff, profile, compiler version and build directory. Configure the
intended profile, record the database hash immediately, and retain exclusive access through
the check. Establish a successful build with current imported interfaces and matching module
artifacts/response files; a previous successful build is sufficient only when its provenance and
unchanged dependencies are known. The selected ordinary TU may have unbuilt edits.

If the database was written by a sibling profile, configure the intended profile again and
re-establish module provenance. If exclusive access or artifact freshness cannot be established,
fall back to Forge's own build, or configure/build a separate directory using `--build-dir`.
Do not wrap Forge in an external lock or promise the standalone check shares Forge's lock.
Copying the database alone does not freeze BMIs, response files, generated headers or includes.

## Run the check

After those gates, use the plugin script (absolute paths):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_translation_unit.py \
  --database <build-dir>/compile_commands.json --profile forge \
  --file <worktree>/Applications/Forge/Source/Private/Forge.cpp --exclusive-profile
```

`--exclusive-profile` acknowledges the prerequisites; it does not discover ownership or acquire
a lock. Re-check the database hash and recorded input state afterward. Any writer or input change
invalidates the result. Do not run the standalone compiler concurrently with a configure/build.

The script requires one exact TU entry, expands response files, keeps compiler/include/module
mappings/semantic flags, removes object/BMI/dependency output flags, bypasses ccache and runs
`-fsyntax-only` with implicit module creation disabled. It never invokes the entry through a shell.
Unknown side-effect modes fail closed. Missing entries, response files or BMIs require Forge;
do not invent include paths or ignore diagnostics. Module-interface changes (`.cppm`) and changed
imported interfaces require Forge to rebuild the dependency closure before a consumer check.

For a diagnostic control, copy the TU to a scratch `.cpp` file, append an intentional syntax/type
error, and pass `--check-copy <scratch.cpp>`. The original directory remains a quoted-include
search path. This proves that compiler diagnostics execute, not production behavior. Keep the
same profile/input prerequisites and confirm Forge-managed outputs are unchanged.

Report: exact file, profile, database path/hash, compiler, provenance/exclusive-access evidence,
exit status/diagnostic, and **syntax/type check only**. Name the remaining Forge verification gates.
