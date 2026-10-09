"""Check one ordinary Clang TU after the recipe's provenance/exclusive-access gates."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


def expand_response(arguments, directory, depth=0):
    if depth > 8:
        raise ValueError("nested response files exceed the supported depth")
    expanded = []
    for argument in arguments:
        if argument.startswith("@"):
            response = directory / argument[1:]
            expanded.extend(expand_response(shlex.split(response.read_text()), directory, depth + 1))
        else:
            expanded.append(argument)
    return expanded


def check_command(entry, source, check_copy=None):
    directory = Path(entry["directory"]).resolve()
    if source.suffix not in (".cpp", ".cc", ".cxx", ".c"):
        raise ValueError("module interfaces require Forge; select an ordinary translation unit")
    arguments = entry.get("arguments") or shlex.split(entry["command"])
    if Path(arguments[0]).name == "ccache":
        arguments = arguments[1:]
    if not Path(arguments[0]).name.startswith(("clang++", "clang-")) and Path(arguments[0]).name != "clang":
        raise ValueError("only a direct Clang compiler command is supported")
    arguments = [arguments[0], *expand_response(arguments[1:], directory)]
    command = [arguments[0]]
    outputs = {"-o", "-MF", "-MT", "-MQ", "-MJ", "-fmodule-output"}
    ignored = {"-c", "-MD", "-MMD", "-MP"}
    index = 1
    sources = 0
    input_pairs = {"-I", "-isystem", "-iquote", "-include", "-imacros", "-D", "-U", "-isysroot", "--sysroot", "-target"}
    semantic_flags = {"-g", "-g0", "-gline-tables-only", "-fPIC", "-fPIE", "-pthread", "-fno-exceptions",
                      "-fno-rtti", "-fno-omit-frame-pointer", "-fomit-frame-pointer", "-fvisibility-ms-compat",
                      "-fvisibility=hidden", "-fvisibility=default", "-ffp-contract=off", "-ffp-contract=fast"}
    while index < len(arguments):
        argument = arguments[index]
        if argument in outputs:
            if index + 1 >= len(arguments):
                raise ValueError("output flag missing its operand")
            index += 2
            continue
        if argument in ignored or argument.startswith("-fmodule-output="):
            index += 1
            continue
        if argument in input_pairs:
            if index + 1 >= len(arguments):
                raise ValueError("input flag missing its operand")
            command.extend(arguments[index:index + 2])
            index += 2
            continue
        if (argument in ("&&", ";", "|", ">", "<", "-Xclang", "-Xpreprocessor", "-emit-llvm", "-S", "-M", "-MM")
                or argument.startswith(("-save-temps", "-Wp,", "-serialize-diagnostics", "-fmodules-cache-path",
                                        "-fprofile", "-ftime-trace", "-fplugin", "-MJ", "-MF", "-MT", "-MQ", "-o="))):
            raise ValueError(f"unsupported side-effect or command flag: {argument}")
        if argument.startswith("-") and not (
                argument in semantic_flags or argument.startswith(("-I", "-D", "-U", "-W", "-std=", "-O",
                                                                   "-fmodule-file=", "-fprebuilt-module-path=",
                                                                   "--sysroot=", "--target=", "-march=", "-mcpu=", "-mtune="))):
            raise ValueError(f"unsupported compiler flag; use Forge: {argument}")
        if not argument.startswith("-") and (directory / argument).resolve() == source:
            sources += 1
            command.append(str(check_copy or source))
        else:
            command.append(argument)
        index += 1
    if sources != 1:
        raise ValueError(f"expected one exact source operand, found {sources}")
    if check_copy:
        command.extend(["-iquote", str(source.parent)])
    command.extend(["-fsyntax-only", "-fno-implicit-modules", "-fno-implicit-module-maps"])
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--exclusive-profile", action="store_true", required=True,
                        help="acknowledge the recipe's provenance and exclusive-access prerequisites")
    parser.add_argument("--check-copy", type=Path)
    parser.add_argument("--show-command", action="store_true")
    options = parser.parse_args()
    source = options.file.resolve()
    entries = json.loads(options.database.read_text())
    matches = [entry for entry in entries
               if (Path(entry["directory"]) / entry["file"]).resolve() == source]
    if len(matches) != 1:
        parser.error(f"expected one database entry for {source}, found {len(matches)}; use Forge")
    entry = matches[0]
    directory = Path(entry["directory"]).resolve()
    if directory != options.database.resolve().parent:
        parser.error("entry directory is foreign to this database; establish profile provenance")
    try:
        command = check_command(entry, source, options.check_copy.resolve() if options.check_copy else None)
        expected_roots = {f"generated-{options.profile}", f"generated-test-{options.profile}",
                          f"generated-trials-{options.profile}"}
        for argument in command:
            if argument.startswith("-I"):
                include = (directory / argument[2:]).resolve()
                if include.is_relative_to(directory):
                    for part in include.relative_to(directory).parts:
                        if part.startswith("generated-") and part not in expected_roots:
                            raise ValueError(f"foreign profile generated root: {part}; configure the intended profile")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Syntax/type check only: {source}; profile={options.profile}; database={options.database.resolve()}", flush=True)
    if options.show_command:
        print(shlex.join(command), flush=True)
    return subprocess.run(command, cwd=entry["directory"], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
