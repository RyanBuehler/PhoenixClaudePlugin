# C++ Tooling Reference

Tool locations, formatter/linter configuration, and command reference for the Phoenix Engine.
For code style and design rules, see `references/style-guide.md`.

## Tool Locations

| Tool/Config | Path | Purpose |
|-------------|------|---------|
| `format.py` | `Tools/format.py` | clang-format wrapper (v20) |
| `tidy.py` | `Tools/tidy.py` | clang-tidy wrapper (v20) |
| `clang_utils.py` | `Tools/clang_utils.py` | Shared utilities |
| `.clang-format` | Root | Formatting rules |
| `.clang-tidy` | Root | Static analysis rules |
| `.editorconfig` | Root | Cross-editor settings |
| CLion Code Style | `.idea/codeStyles/Project.xml` | IDE formatting |
| CLion Inspections | `.idea/inspectionProfiles/Phoenix.xml` | IDE analysis |

## Quick Command Reference

```bash
# Format staged files and verify
python3 Tools/format.py --files=staged
python3 Tools/format.py --files=staged -error

# Format files changed since branching from main
python3 Tools/format.py --files=branch
python3 Tools/format.py --files=branch -error

# Dry run (preview without modifying)
python3 Tools/format.py --files=staged -n

# Run clang-tidy on branch changes
python3 Tools/tidy.py --files=branch

# Generate compilation database first (required for tidy)
python3 Tools/tidy.py --compdb

# Skip test files
python3 Tools/tidy.py --filter '*Trials.cpp'

# Adjust warning limit
python3 Tools/tidy.py --limit 10
```

## The Formatting Stack

### Layer 1: `.editorconfig` (Universal Baseline)
```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_size = 4
indent_style = tab

[*.{yml,yaml}]
indent_style = space
indent_size = 2
```

### Layer 2: `.clang-format` (C/C++ Formatting - Source of Truth)

**Key Settings:**
- Based on LLVM style with extensive customizations
- **Tab-based indentation** (tab width: 4)
- **Column limit: 120** (hard wrap)
- **Namespace indentation: All** (contents indented)
- **Brace style: Custom Allman-like** (braces on own line for classes, functions, control statements)
- **Pointer/reference alignment: Left** (`int* ptr`, not `int *ptr`)
- **Include ordering: Regroup** with priority system (PhoenixPCH.h first)

**Include Priority Order:**
1. `"PhoenixPCH.h"` (priority 0)
2. `"LocalHeader.h"` - headers without path separators (priority 1)
3. `"path/to/Header.h"` - project headers with paths (priority 2)
4. `<system>` - system/library headers (priority 3)
5. Everything else (priority 4)

**Brace Wrapping (All True):**
- AfterClass, AfterControlStatement, AfterEnum, AfterFunction
- AfterNamespace, AfterStruct, AfterUnion
- BeforeCatch, BeforeElse, BeforeLambdaBody, BeforeWhile

**Formatting Decisions:**
- `BinPackArguments: false` - Each argument on own line when wrapping
- `BinPackParameters: OnePerLine` - Each parameter on own line when wrapping
- `PackConstructorInitializers: Never` - Each initializer on own line
- `SpaceAfterCStyleCast: true` - `(int) x` not `(int)x`
- `SeparateDefinitionBlocks: Always` - Blank line between definitions
- `AllowShortIfStatementsOnASingleLine: WithoutElse` - Short if statements allowed inline

### Layer 3: `.clang-tidy` (Static Analysis - Warnings as Errors)

**Enabled Check Categories:**
- `bugprone-*` - Common bug patterns
- `cppcoreguidelines-*` - C++ Core Guidelines
- `modernize-*` - Modern C++ opportunities
- `performance-*` - Performance improvements
- `readability-*` - Code clarity (except implicit-bool-conversion)
- `clang-analyzer-*` - Static analysis
- `portability-*` - Cross-platform issues (except pragma-once)
- `hicpp-*` - High Integrity C++ (except noexcept-related)
- `misc-unused-parameters` - Unused parameter detection

**Disabled Checks (Project Policy):**
- `modernize-use-auto` / `hicpp-use-auto` - Explicit types preferred
- `modernize-use-trailing-return-type` - Traditional style preferred
- `modernize-use-noexcept` / `hicpp-use-noexcept` - Exceptions forbidden
- `cppcoreguidelines-avoid-do-while` - Do-while allowed
- `cppcoreguidelines-pro-type-reinterpret-cast` - Reinterpret cast allowed
- `portability-avoid-pragma-once` - Pragma once required

**Warnings Treated as Errors:**
- `bugprone-*`
- `cppcoreguidelines-*`
- `modernize-*`
- `performance-*`

**Header Filter:** `^(Core|Modules|Plugins)/` - Only analyze project headers

### Layer 4: Naming Conventions (Enforced by clang-tidy)

| Identifier Type | Pattern | Example |
|-----------------|---------|---------|
| Classes, Structs, Unions, Enums | `^[A-Z][a-zA-Z0-9]*$` | `MyClass` |
| Functions, Methods | `^[A-Z][a-zA-Z0-9]*$` | `ProcessData` |
| Variables | `^(?:[baps]+)?[A-Z][A-Za-z0-9]*$` | `Count`, `bIsEnabled` |
| Local Variables | `^[ijk]$\|^(?:[baps]+)?[A-Z][A-Za-z0-9]*$` | `i`, `Name` |
| Parameters | `^[ijk]$\|^(?:[baps]+)?[A-Z][A-Za-z0-9]*$` | `InputData` |
| Private/Protected Members | `^m_(?:[baps]*)[A-Z][A-Za-z0-9]*$` | `m_Value`, `m_bActive` |
| Public Members | `^m_[A-Z][a-zA-Z0-9]*$` | `m_Name` |
| Static Variables | `^s_[bap]*[A-Z][A-Za-z0-9]*$` | `s_Instance` |
| Global Variables | `^g_(?:[baps]*)[A-Z][A-Za-z0-9]*$` | `g_Settings` |
| Constants, Constexpr | `^[A-Z][A-Z0-9_]*$` or CamelCase | `MAX_SIZE`, `Value` |
| Enumerators | `^[A-Z][a-zA-Z0-9]*$` | `Red`, `Green` |
| Macros | `^[A-Z][A-Z0-9_]*$` | `MY_MACRO` |
| Namespaces | `^[A-Z][a-zA-Z0-9]*$` | `Core`, `Engine` |
| Template Parameters | `^[A-Z][a-zA-Z0-9]*$` | `T`, `Container` |

**Hungarian Notation Prefixes (Optional for Variables):**
- `b` - Boolean
- `a` - Array
- `p` - Pointer
- `s` - String

### Layer 5: CLion IDE Configuration

**Code Style (`.idea/codeStyles/Project.xml`):**
- Tab-based indentation across C++, CMake, JSON, Python
- Wrap limit: 160 (looser than clang-format's 120 for IDE comfort)
- Aligns multiline arguments, parameters, extends lists
- Namespace indentation: All
- Brace style: End of line (differs from clang-format - clang-format is authoritative)

**Inspection Profile (`.idea/inspectionProfiles/Phoenix.xml`):**
- Most C++ inspections disabled to reduce noise
- Enabled structural checks:
  - `CppEnforceCVQualifiersOrder` - Const placement
  - `CppEnforceCVQualifiersPlacement` - Const placement
  - `CppEnforceDoStatementBraces` - Braces on do-while
  - `CppEnforceForStatementBraces` - Braces on for
  - `CppEnforceIfStatementBraces` - Braces on if
  - `CppEnforceWhileStatementBraces` - Braces on while
  - `CppEnforceTypeAliasCodeStyle` - Using over typedef
  - `CppRemoveRedundantBraces` - Remove unnecessary braces
- ClangTidy integration disabled (`-*`) to avoid duplicate warnings

## Tool Architecture

### `clang_utils.py` - Shared Utilities

```python
# File selection functions
get_staged_files()   # git diff --name-only --cached
get_branch_files()   # git diff --name-only $(git merge-base HEAD main)
get_all_files()      # git ls-files

# Filtering functions
filter_cpp(files)    # .c, .cc, .cpp, .cxx, .h, .hpp, .hxx
filter_tidy(files)   # .c, .cc, .cpp, .cxx (sources only, no headers)

# Tool management
ensure_tool(exe, package)  # Auto-install via pip if missing
```

### `format.py` - clang-format Wrapper

**Command-line Options:**
- `--files={staged,branch,all}` - File selection mode (default: branch)
- `-n, --dry-run` - Preview without modifying
- `-e, --error` - Fail if changes needed (CI mode)
- `--clang-format=PATH` - Custom executable
- `-f, --filter=PATTERN` - Skip files matching wildcard
- `--system-headers` - Include system headers

### `tidy.py` - clang-tidy Wrapper

**Command-line Options:**
- `--files={staged,branch,all}` - File selection mode (default: branch)
- `-c, --compdb` - Generate compile_commands.json
- `-p, --build-dir=PATH` - Build directory (default: build)
- `--limit=N` - Stop after N files with warnings (default: 5)
- `--clang-tidy=PATH` - Custom executable
- `-f, --filter=PATTERN` - Skip files matching wildcard

## Common Issues & Solutions

### "No files to process"
- Check `--files` mode - are there actually staged/branch changes?
- Ensure files have proper extensions (.cpp, .h, etc.)

### "Compilation database not found"
```bash
python3 Tools/tidy.py --compdb
# Or manually:
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DTESTS=ON
```

### Formatting differs between CLI and IDE
- **clang-format is authoritative** - CLI tools are the source of truth
- CLion uses its own formatter by default; it should be configured to use clang-format
- Check `.clang-format` version compatibility (requires clang-format 20)

### clang-tidy false positives
- Check if the file has a local `.clang-tidy` override (e.g., in submodules)
- Some checks may need explicit suppression via `// NOLINT` (use sparingly)
- Verify the header filter regex matches your files

## Version Requirements

- **clang-format**: 20.x (installed via `pip install clang-format`)
- **clang-tidy**: 20.x (installed via `pip install clang-tidy`)
- **Python**: 3.x with pathlib support
- **CMake**: Required for compilation database generation
