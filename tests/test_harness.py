"""Offline regression tests for the harness quality gates."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / "harness" / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load harness script: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessTests(unittest.TestCase):
    def run_harness(self, args, test_code=0):
        runner = load_script("run_harness")
        with tempfile.TemporaryDirectory() as directory:
            feedback = Path(directory) / "feedback.md"
            with patch.object(runner, "FEEDBACK_FILE", feedback), patch.object(
                runner, "run_cmd", side_effect=[(0, ""), (0, ""), (test_code, "test output")]
            ) as command, patch("sys.argv", ["run_harness.py", *args]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    runner.main()
                return command.call_args_list[-1], result.exception.code, feedback.exists()

    def test_default_runs_full_pytest_discovery(self):
        call, code, _ = self.run_harness([])
        self.assertEqual(call.args[0][1:], ["-m", "pytest", "-q", "--tb=short"])
        self.assertEqual(call.kwargs["env"], {"SKIP_LIVE": "1", "ALLOW_LOCAL_RUN": "0"})
        self.assertEqual(code, 0)

    def test_explicit_target_is_preserved(self):
        call, _, _ = self.run_harness(["tests/test_ai.py"])
        self.assertEqual(call.args[0][3], "tests/test_ai.py")

    def test_test_failure_fails_harness_and_writes_feedback(self):
        _, code, feedback_exists = self.run_harness([], test_code=1)
        self.assertEqual(code, 1)
        self.assertTrue(feedback_exists)

    def test_wrapper_defaults_to_full_suite(self):
        wrapper = (ROOT / "scripts/harness/harness.ps1").read_text(encoding="utf-8")
        self.assertIn('[string]$Target = ""', wrapper)

    def check_function_gate(self, body_lines, expected_code):
        verifier = load_script("verify_standards")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "sample.py").write_text(
                "def sample():\n" + "    value = 1\n" * body_lines, encoding="utf-8"
            )
            with patch.object(verifier, "TARGET_DIRS", [str(target)]), patch(
                "sys.argv", ["verify_standards.py", "--markdown"]
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    verifier.main()
                self.assertEqual(result.exception.code, expected_code)

    def test_oversized_function_fails_without_file_length_violation(self):
        self.check_function_gate(60, 1)

    def test_function_at_limit_passes(self):
        self.check_function_gate(59, 0)


if __name__ == "__main__":
    unittest.main()
