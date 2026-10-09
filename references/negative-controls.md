# Negative controls

For each claimed behavior, record: production dispatch path, observable setup, executed case,
intended assertion, and mutation. The setup must distinguish correct behavior from the broken
behavior; an assertion true by construction is not a witness. Distinct custom-write, reflective,
and JSON-override paths need witnesses on those paths. One witness can cover several claims when
the same observable behavior proves them; do not add redundant control legs.

1. Start with the passing fixed tree. Record the baseline diff and back up the exact bytes of
   every file the control will mutate, including uncommitted edits. Arm cleanup before mutation
   with `try/finally` and interrupt handling, or an EXIT/INT/TERM trap. Keep the backup until
   byte-for-byte restoration is confirmed. SIGKILL cannot run cleanup: prefer a disposable
   worktree for interrupt-prone work, and check restoration before resuming after interruption.
2. Mutate the operation that produces the behavior, at the intended location, and assert the
   expected match count before writing. Inspect the mutation diff. For generator claims, mutate
   the producer and regenerate through its real invocation; changing only its output proves
   artifact checking, not producer behavior. Rebootstrap if the producer is compiled into Forge.
3. Build the mutated code successfully in the correct profile. A failed edit, configure,
   compiler, or stale-binary refusal is unavailable behavioral proof, not a successful control.
4. Run the named binary with `--list-cases --output-on-failure --require-executed-cases`.
   Confirm the actual case executed and failed at the intended assertion for the expected reason.
   An unrelated red case proves nothing about this witness.
5. Batch mutations only if each retains a separately visible failing assertion. If `REQUIRES`
   aborts the case at its first failure, use separate runs from restored baseline; later assertions
   in that same case are masked. A nearby easy dispatch path cannot stand in for the claimed path.
6. Restore the saved bytes even after an error or interruption, confirm bytes and baseline diff,
   rebuild restored code and confirm green. Re-arm affected witnesses after later code/test edits.

Report one row per witness: claim/path | mutation and match count | profile/build result |
actual executed case | intended failing assertion and observed diagnostic | restoration/green.
Label source inspection as **structural** and inferred behavior as **deduced** when a behavioral
witness cannot run. Neither is a substitute for a required executed control.
