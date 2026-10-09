import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import shutil
import subprocess
import sys


class TranslationUnitTests(unittest.TestCase):
    def load_tool(self):
        spec = importlib.util.spec_from_file_location(
            "check_translation_unit", Path(__file__).parents[1] / "scripts/check_translation_unit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_preserves_inputs_and_removes_all_outputs_in_response_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "unit.cpp"
            source.write_text("int value;\n")
            (directory / "unit.modmap").write_text(
                "-fmodule-file=Phoenix.Core=Core.pcm -fmodule-output=unit.pcm")
            entry = {"directory": temporary, "file": str(source), "command":
                     f"clang++ -std=c++23 -Iinclude -DVALUE=1 @unit.modmap -MD -MF unit.d -MT unit.o -o unit.o -c {source}"}
            command = self.load_tool().check_command(entry, source)
            self.assertIn("-fmodule-file=Phoenix.Core=Core.pcm", command)
            self.assertIn("-std=c++23", command)
            self.assertIn("-Iinclude", command)
            self.assertIn("-DVALUE=1", command)
            self.assertIn("-fsyntax-only", command)
            self.assertNotIn("-c", command)
            self.assertFalse(any("unit.o" in argument or "unit.d" in argument or
                                 "unit.pcm" in argument for argument in command))

    def test_rejects_modules_shell_and_hidden_output_flags(self):
        tool = self.load_tool()
        for command, filename in [("clang++ -c unit.cppm", "unit.cppm"),
                                  ("clang++ -c unit.cpp && touch marker", "unit.cpp"),
                                  ("clang++ -Xclang -emit-pch -c unit.cpp", "unit.cpp"),
                                  ("clang++ -save-temps -c unit.cpp", "unit.cpp"),
                                  ("clang++ --serialize-diagnostics unit.dia -c unit.cpp", "unit.cpp"),
                                  ("clang++ --config=hidden.cfg -c unit.cpp", "unit.cpp"),
                                  ("clang++ -funknown-output=unit.pcm -c unit.cpp", "unit.cpp")]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                tool.check_command({"directory": "/tmp", "file": filename,
                                    "command": command}, Path("/tmp") / filename)

    @unittest.skipUnless(shutil.which("clang++"), "Clang is required for the executed syntax check")
    def test_real_compiler_accepts_valid_copy_rejects_error_and_writes_no_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "unit.cpp"
            source.write_text("int value = 1;\n")
            database = directory / "compile_commands.json"
            database.write_text(json.dumps([{"directory": temporary, "file": str(source),
                "arguments": [shutil.which("clang++"), "-std=c++23", "-MD", "-MF", "unit.d",
                              "-o", "unit.o", "-c", str(source)]}]))
            script = Path(__file__).parents[1] / "scripts/check_translation_unit.py"
            command = [sys.executable, str(script), "--database", str(database), "--profile", "forge",
                       "--file", str(source), "--exclusive-profile"]
            good = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            broken = directory / "broken.cpp"
            broken.write_text(source.read_text() + "int invalid = ;\n")
            bad = subprocess.run(command + ["--check-copy", str(broken)], capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("expected expression", bad.stderr)
            self.assertFalse((directory / "unit.o").exists())
            self.assertFalse((directory / "unit.d").exists())

    def test_foreign_generated_profile_and_missing_entry_refuse_before_compilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "unit.cpp"
            database = directory / "compile_commands.json"
            entry = {"directory": temporary, "file": str(source),
                     "arguments": ["clang++", f"-I{directory}/generated-editor", "-c", str(source)]}
            database.write_text(json.dumps([entry]))
            script = Path(__file__).parents[1] / "scripts/check_translation_unit.py"
            command = [sys.executable, str(script), "--database", str(database), "--profile", "forge",
                       "--file", str(source), "--exclusive-profile"]
            foreign = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(foreign.returncode, 0)
            self.assertIn("foreign profile", foreign.stderr)
            database.write_text("[]")
            missing = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("found 0", missing.stderr)


if __name__ == "__main__":
    unittest.main()
