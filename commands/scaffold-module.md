---
description: Create a new Phoenix engine module using the project's create_module.py scaffolding tool.
---

Create a new module using the project's scaffolding tool. Supports interactive and non-interactive modes.

## Arguments

- **`<name>`** — *(optional)* module name for non-interactive mode
- **`<type>`** — *(optional)* module type: `Module`, `Plugin`, `External`, or `Submodule`

## 1. Run Scaffolding Tool

**Interactive mode** (no arguments):

```bash
python3 Tools/create_module.py
```

**Non-interactive mode** (arguments provided):

```bash
python3 Tools/create_module.py --name <NAME> --type <TYPE>
```

Additional flags for non-interactive mode:
- `--deps Core,Engine` — specify dependencies
- `--parent <MODULE> --parent-type Module` — for submodules

## 2. Report

Tell the user what was created — the directory structure, CMakeLists.txt, description JSON, and initial source/header/trial files.
