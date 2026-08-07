# Formatting — Phoenix Rules

**Everything in this document is enforced mechanically by clang-format.** It is here so a
reader can look up what the formatter will do, not so anyone has to check it by hand.

**Audit never reads this file.** A misformatted file is not drift, it is an unformatted
file — the finding is always "run `/phoe:format`", never a list of lines. `references/style-guide.md`
holds the rules that require judgment.

## What the formatter decides

| Rule | `.clang-format` |
|---|---|
| Lines limited to 150 characters | `ColumnLimit: 150` |
| Tabs, width four | `UseTab: ForContinuationAndIndentation`, `TabWidth: 4` |
| Allman braces — opening brace on its own line | `BreakBeforeBraces: Custom` |
| Consecutive assignments, declarations, bitfields, and short case statements aligned | `AlignConsecutive*` |
| Trailing comments aligned | `AlignTrailingComments` |
| Includes sorted case-insensitively and regrouped by category | `SortIncludes: CaseInsensitive`, `IncludeBlocks: Regroup`, `IncludeCategories` |
| A blank line between definition blocks | `SeparateDefinitionBlocks: Always` |
| At most one consecutive blank line | `MaxEmptyLinesToKeep: 1` |
| A blank line before an access modifier that opens a logical block | `EmptyLineBeforeAccessModifier: LogicalBlock` |

The include categories carry a deliberate quirk: `*Forward.inl` fragments sort ahead of
everything, including the main header, so their global-module forward declarations precede
the first `import`. That accommodation exists for g++'s `import std` and is commented in
`.clang-format` itself.

## Bypassing it

A `// clang-format off` region requires an adjacent comment saying why, the same as any
lint bypass (`comments.md` C14). A bypass with no stated reason cannot be told apart from
a mistake.

## The gap

`SeparateDefinitionBlocks` separates **definitions** — functions, classes, structs, enums,
namespaces. It does not touch control-flow blocks inside a function body, so the blank line
after a closing `}` of an `if`, `for`, `while`, or lambda body is **not** mechanical. That
rule, and the judgment about when an `if` should carry an init-statement instead, live in
`style-guide.md` §Formatting Residue.
