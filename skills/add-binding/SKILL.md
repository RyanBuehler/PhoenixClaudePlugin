---
name: add-binding
description: Use when adding a new controllable feature, control, menu item, shortcut or binding to Phoenix. Not for a new parameter on an existing binding.
---

# Add a binding

Every Editor operation is one Symbiote binding. Python, the console, the agent action, a user
control and (when run-time callable) a Neuron are projections of that one declaration. This skill
is the order of work. The mechanics live in the Phoenix repo's `Docs/BindingDeclaration_DD.md`;
read its section 2 (the declaration) and the Status paragraph on adding a later action before
writing the row. `Docs/Symbiote_DD.md` section 0 is the rule this follows.

This skill does not apply to a new parameter on an existing binding; edit that row in place.

## 1. Decide whether it is a binding

- Does a user control do this? Then it has exactly one binding, and the control invokes it.
- Can it be written as Python over existing bindings? Then it is neither a binding nor a tool.
  Compositions and conveniences are Python, never new bindings.
- Search the surface first (`dispatch.actions.search`, or `git grep` the binding key) so you do not
  declare a second path to an existing operation.

## 2. Ask the gate, then keep working

Ask Ryan one AskUserQuestion that covers both decisions: whether to add the binding, and its key.

- The key is `<domain>.<action>`. Domains namespace by area, often the owning module. Propose the
  subject first (`realm.create`, `soul.seal`), and name the domain plainly in the question.
- A new domain needs Ryan's approval; say in the question that the domain is new.
- Explain the feature and what the key names inside the question, with an example call.

Keep working on the rest of the procedure while the question is pending. An unanswered question
is not consent: do not ship, and do not write that Ryan approved, until he answers.

## 3. Declare the row in the owning module's table

The declaration lives beside its function, in the table of the module that supports it. An
Editor-only binding lives in the Editor or the module's editor companion (`<Module>Editor`), never
in a runtime module a cooked game links.

- Spell every designator, in declaration order. An omitted one compiles and value-initializes,
  so a missing `.Security` reads `Safe`.
- `Description`: one sentence for the agent and the palette, plus a sentence that names each
  refusal code the row declares. The catalog trials fail a code the description leaves out.
- `Tags`: at least one word from the fixed vocabulary (`BindingTag` in
  `Engine/Core/Public/Interface/Binding.cppm`), never free text.
- `Security`, `bRuntimeCallable` and `bCyclePure` are decisions, not defaults. `bCyclePure` is
  true only when the function is shown to touch nothing the cycle walks. No agent or tool work runs
  inline on the cycle thread.

## 4. Register and generate

- The module registers its table through `RegisterBindingTable` from its own entry point.
  Modules own their declarations; no consumer lists modules by hand.
- Run `python3 Tools/generate_bindings.py --write`. No `Registrar.Bind` line is written by hand.
- A module declaring its first table has more to do; the DD's Status section lists it.

## 5. Wire the control

The control only invokes the binding, by key. UI invokes, bindings report: the control carries no
warning, log line or refusal wording of its own. The binding reports its own failures. The control
parity trial checks that the control only invokes its binding.

## 6. Trials

- Drive the real path: invoke the binding as a caller would. No source-text trials, and no
  production seam that only a trial calls.
- Claim every WARN and ERROR a case logs.

## 7. Names

- Run `python3 Tools/Audit/naming.py` from the worktree root.
- Confirm every new production name with Ryan before the work ships: the binding key, its
  parameters and refusal codes, and any new C++ symbol.
