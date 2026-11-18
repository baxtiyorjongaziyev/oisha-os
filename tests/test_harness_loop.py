"""Offline tests for the autonomous harness loop (scripts/harness/agent_loop.py)."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_loop():
    spec = importlib.util.spec_from_file_location(
        "harness_agent_loop", ROOT / "scripts" / "harness" / "agent_loop.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HarnessLoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = load_loop()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(self.loop, "FEEDBACK_FILE", Path(tmp.name) / "feedback.md")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_last_iteration_does_not_run_unverified_agent(self):
        code, audits, agents = self.run_loop([(1, "")], [], max_iterations=1)
        self.assertEqual((code, audits, agents), (1, 1, 0))

    def test_windows_split_strips_grouping_quotes(self):
        with patch.object(self.loop.os, "name", "nt"):
            args = self.loop.split_agent_cmd('"C:\\Program Files\\a.exe" -p "fix it"')
        self.assertEqual(args, ["C:\\Program Files\\a.exe", "-p", "fix it"])

    def run_loop(self, audits, states, agent_cmd="fix", safe=True, **kw):
        config = self.loop.LoopConfig(agent_cmd=agent_cmd, **kw)
        with patch.object(self.loop, "assert_safe_environment", return_value=safe), \
             patch.object(self.loop, "execute_audit", side_effect=audits) as audit, \
             patch.object(self.loop, "get_git_state", side_effect=states), \
             patch.object(self.loop, "run_agent_step", return_value=0) as agent, \
             patch.object(self.loop, "record_successful_handoff"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = self.loop.run_autonomous_loop(config)
        return code, audit.call_count, agent.call_count

    def test_green_first_audit_skips_agent(self):
        code, audits, agents = self.run_loop([(0, "")], [])
        self.assertEqual((code, audits, agents), (0, 1, 0))

    def test_agent_fix_then_green(self):
        code, audits, agents = self.run_loop([(1, ""), (0, "")], ["a", "b"])
        self.assertEqual((code, audits, agents), (0, 2, 1))

    def test_no_agent_cmd_runs_single_audit(self):
        code, audits, agents = self.run_loop([(1, "")], [], agent_cmd=None)
        self.assertEqual((code, audits, agents), (1, 1, 0))

    def test_stalling_agent_trips_circuit_breaker(self):
        code, audits, agents = self.run_loop(
            [(1, "")] * 10, ["same"] * 20, max_stalls=3
        )
        self.assertEqual((code, audits, agents), (1, 3, 3))

    def test_progress_resets_stall_counter(self):
        states = ["a", "a", "a", "b", "b", "b", "b", "b"]
        code, audits, _ = self.run_loop([(1, "")] * 5, states, max_iterations=5, max_stalls=2)
        self.assertEqual((code, audits), (1, 4))

    def test_refuses_on_main(self):
        code, audits, _ = self.run_loop([(0, "")], [], safe=False)
        self.assertEqual((code, audits), (2, 0))

    def test_default_target_is_full_suite(self):
        self.assertIsNone(self.loop.parse_args([]).test_target)
        config = self.loop.parse_args(["tests/x.py", "--agent-cmd", "claude -p fix"])
        self.assertEqual((config.test_target, config.agent_cmd), ("tests/x.py", "claude -p fix"))


if __name__ == "__main__":
    unittest.main()
