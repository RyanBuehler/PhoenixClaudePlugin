# Modern Python Quick Reference (3.10+)

Practical reference for Python scripts in a C++ build toolchain context.

> **Project convention:** This project uses **tabs** for Python indentation, not spaces.

## Python 3.10 — Structural Pattern Matching

### match Statements

Replaces long if/elif chains for type and value checking.

```python
match command:
	case "build":
		run_build()
	case "test" | "check":
		run_tests()
	case str(s) if s.startswith("--"):
		parse_flag(s)
	case _:
		print(f"Unknown: {command}")
```

**Replaces:** `if command == "build": ... elif command == "test": ...`

### Matching with Destructuring

```python
match result:
	case {"status": "ok", "data": data}:
		process(data)
	case {"status": "error", "message": msg}:
		log_error(msg)
```

### Parenthesized Context Managers

```python
with (
	open("input.txt") as infile,
	open("output.txt", "w") as outfile,
):
	outfile.write(infile.read())
```

**Replaces:** backslash line continuation or nested `with` blocks.

## Python 3.11 — Error Handling & Performance

### Fine-Grained Error Locations

Tracebacks now point to the exact expression, not just the line:

```
Traceback:
    result = x["key1"]["key2"]
                       ^^^^^^^^
KeyError: 'key2'
```

### tomllib (Built-In TOML Parsing)

```python
import tomllib

with open("config.toml", "rb") as f:
	config = tomllib.load(f)
```

**Replaces:** third-party `toml` or `tomli` packages.

### ExceptionGroup and except*

```python
# Catching multiple concurrent exceptions
try:
	results = run_parallel_tasks()
except* ValueError as eg:
	for exc in eg.exceptions:
		handle_value_error(exc)
except* OSError as eg:
	for exc in eg.exceptions:
		handle_os_error(exc)
```

## Python 3.12 — Type Syntax & F-Strings

### Type Parameter Syntax

```python
# New: Type parameter syntax (PEP 695)
type Vector[T] = list[T]

def first[T](items: list[T]) -> T:
	return items[0]

class Stack[T]:
	def push(self, item: T) -> None: ...
	def pop(self) -> T: ...
```

**Replaces:** `from typing import TypeVar; T = TypeVar('T')`

### Improved F-Strings

F-strings can now contain any valid Python expression, including nested quotes and backslashes:

```python
# Nested quotes (previously required alternating quote styles)
print(f"{'hello'!r}")
print(f"{dict['key']}")

# Multi-line expressions
msg = f"result: {
	some_long_function_call(
		arg1, arg2
	)
}"
```

## Python 3.13 — Performance

### Free-Threaded Mode (Experimental)

Run without the GIL for true parallelism:

```bash
python3.13t script.py  # Free-threaded build
```

### JIT Compiler (Experimental)

Copy-and-patch JIT for performance-critical code paths. Enabled via:

```bash
PYTHON_JIT=1 python3.13 script.py
```

## Essential Modern Patterns

### pathlib Over os.path

```python
from pathlib import Path

# Old
import os
path = os.path.join(base, "src", "file.cpp")
ext = os.path.splitext(path)[1]
files = [f for f in os.listdir(d) if f.endswith(".cpp")]

# New
path = Path(base) / "src" / "file.cpp"
ext = path.suffix
files = list(Path(d).glob("*.cpp"))

# Common operations
path.exists()
path.is_file()
path.is_dir()
path.stem          # filename without extension
path.name          # filename with extension
path.parent        # parent directory
path.read_text()   # read entire file
path.write_text(s) # write entire file
path.mkdir(parents=True, exist_ok=True)
path.resolve()     # absolute path
path.relative_to(base)
```

### Built-In Generic Types (3.9+)

```python
# Old (requires typing imports)
from typing import List, Dict, Optional, Tuple, Set

def process(items: List[str]) -> Dict[str, int]: ...
def find(x: Optional[str] = None) -> Tuple[int, ...]: ...

# New (use built-in types directly)
def process(items: list[str]) -> dict[str, int]: ...
def find(x: str | None = None) -> tuple[int, ...]: ...
```

### Walrus Operator (:=)

```python
# Old
line = f.readline()
while line:
	process(line)
	line = f.readline()

# New
while (line := f.readline()):
	process(line)

# In comprehensions
results = [
	cleaned
	for raw in data
	if (cleaned := clean(raw)) is not None
]
```

### Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class BuildConfig:
	name: str
	build_type: str = "Release"
	flags: list[str] = field(default_factory=list)
	tests: bool = True

# Auto-generates __init__, __repr__, __eq__
config = BuildConfig("Linux", flags=["-Wall"])
```

### Protocol (Structural Subtyping)

```python
from typing import Protocol

class Formattable(Protocol):
	def format(self, spec: str) -> str: ...

# Any class with a format() method satisfies this
# No explicit inheritance required
def display(obj: Formattable) -> None:
	print(obj.format("pretty"))
```

## CLI Tool Patterns

### argparse Best Practices

```python
import argparse

def main():
	parser = argparse.ArgumentParser(description="Format C++ files")
	parser.add_argument(
		"--files",
		choices=["staged", "branch", "all"],
		default="branch",
		help="file selection mode",
	)
	parser.add_argument(
		"-e", "--error",
		action="store_true",
		help="fail if changes needed",
	)
	parser.add_argument(
		"-f", "--filter",
		help="skip files matching pattern",
	)
	args = parser.parse_args()
	# Use args.files, args.error, args.filter
```

### subprocess.run

```python
import subprocess

# Simple command
result = subprocess.run(
	["cmake", "--build", "build", "--config", "Release"],
	capture_output=True,
	text=True,
)

if result.returncode != 0:
	print(f"Build failed:\n{result.stderr}")

# With shell=False (safer, preferred)
result = subprocess.run(
	["git", "diff", "--name-only", "--cached"],
	capture_output=True,
	text=True,
	check=False,  # Don't raise on non-zero exit
)
files = result.stdout.strip().splitlines()
```

### shutil for File Operations

```python
import shutil

shutil.copy2(src, dst)         # Copy with metadata
shutil.copytree(src, dst)      # Copy directory tree
shutil.rmtree(path)            # Remove directory tree
shutil.which("clang-format")   # Find executable in PATH
shutil.move(src, dst)          # Move file/directory
```

## File Handling

### Context Managers for Files

```python
# Always use context managers
with open("file.txt", encoding="utf-8") as f:
	content = f.read()

# Binary mode for non-text files
with open("data.bin", "rb") as f:
	data = f.read()

# Writing with explicit encoding
with open("output.txt", "w", encoding="utf-8") as f:
	f.write(content)
```

### Temporary Files

```python
import tempfile

with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False) as tmp:
	tmp.write(b"// temp file")
	tmp_path = Path(tmp.name)

with tempfile.TemporaryDirectory() as tmpdir:
	# tmpdir is automatically cleaned up
	build_dir = Path(tmpdir) / "build"
```

## Performance Tips

### Generator Expressions Over Lists

```python
# Bad: Creates entire list in memory
total = sum([len(line) for line in lines])

# Good: Generator (lazy evaluation)
total = sum(len(line) for line in lines)

# Good: any/all with generators
has_errors = any(line.startswith("ERROR") for line in log)
all_pass = all(test.passed for test in results)
```

### set for Membership Testing

```python
# Bad: O(n) lookup
cpp_exts = [".cpp", ".cc", ".cxx", ".c"]
if ext in cpp_exts: ...

# Good: O(1) lookup
CPP_EXTS = {".cpp", ".cc", ".cxx", ".c"}
if ext in CPP_EXTS: ...
```

### str.join Over Concatenation

```python
# Bad: O(n^2) string concatenation
result = ""
for line in lines:
	result += line + "\n"

# Good: O(n) join
result = "\n".join(lines)
```

### functools.cache

```python
from functools import cache, lru_cache

@cache  # Unlimited cache (3.9+)
def find_tool(name: str) -> Path | None:
	return shutil.which(name)

@lru_cache(maxsize=128)  # Bounded cache
def parse_config(path: str) -> dict:
	...
```

## Common Patterns for Build Scripts

### Running Commands with Error Handling

```python
def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
	result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
	if result.returncode != 0:
		print(f"Command failed: {' '.join(cmd)}")
		print(result.stderr)
	return result
```

### Filtering Files by Extension

```python
def filter_cpp(files: list[Path]) -> list[Path]:
	CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"}
	return [f for f in files if f.suffix in CPP_EXTS]
```

### Getting Git File Lists

```python
def get_staged_files() -> list[Path]:
	result = subprocess.run(
		["git", "diff", "--name-only", "--cached"],
		capture_output=True, text=True,
	)
	return [Path(f) for f in result.stdout.strip().splitlines() if f]
```
