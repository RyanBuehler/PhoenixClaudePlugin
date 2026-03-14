---
description: Run clang-tidy on changed files. Generates compilation database if needed.
---

Run clang-tidy:

```bash
python Tools/tidy.py
```

If the compilation database is missing (`build/compile_commands.json` not found), generate it first:

```bash
python Tools/tidy.py --compdb
python Tools/tidy.py
```

Report any warnings or errors found. Test files (`*Trials.cpp`) may be skipped with `--filter '*Trials.cpp'` if the user requests.
