---
description: Run clang-tidy on changed files. Generates compilation database if needed.
---

Run clang-tidy on changed files, generating the compilation database first if missing.

## 1. Check Compilation Database

If `build/compile_commands.json` is missing, generate it:

```bash
python Tools/tidy.py --compdb
```

## 2. Lint

```bash
python Tools/tidy.py
```

Test files (`*Trials.cpp`) may be skipped with `--filter '*Trials.cpp'` if the user requests.

## 3. Report

Tell the user about any warnings or errors found, or confirm a clean run.
