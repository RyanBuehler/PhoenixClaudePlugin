---
description: Create a new Phoenix engine module using the project's create_module.py scaffolding tool.
---

Use the project's existing module scaffolding tool:

```bash
python Tools/create_module.py
```

This runs in interactive mode and prompts for module name, type (Module, Plugin, External, Submodule), parent module (for submodules), and dependencies.

For non-interactive usage:

```bash
# Create a module
python Tools/create_module.py --name MyModule --type Module

# Create a plugin
python Tools/create_module.py --name MyPlugin --type Plugin --deps Core,Engine

# Create a submodule under an existing module
python Tools/create_module.py --name MySub --type Submodule --parent Engine --parent-type Module
```

The tool creates the full directory structure, CMakeLists.txt, description JSON, and initial source/header/trial files following project conventions.
