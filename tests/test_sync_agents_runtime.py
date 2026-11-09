"""Tests for scripts/sync_agents_runtime.py."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import MagicMock, patch

from scripts import sync_agents_runtime


class TestSyncAgentsRuntime(unittest.TestCase):
    """Test suite for agents runtime synchronization."""

    def test_update_openclaw_config_file_creates_and_updates(self) -> None:
        """Test updating openclaw.json with Gemini 2.5 Flash as primary and Groq fallback."""
        tmp_dir = Path("tmp_test_openclaw")
        tmp_dir.mkdir(exist_ok=True)
        cfg_file = tmp_dir / "openclaw.json"
        try:
            initial_data = {
                "agents": {"defaults": {"model": "old-model"}},
                "existing_key": "preserved_val",
                "models": {
                    "providers": {
                        "google": {"apiKey": {"source": "env", "id": "GEMINI_API_KEY"}},
                        "groq": {"apiKey": {"source": "env", "id": "GROQ_API_KEY"}},
                    }
                },
            }
            cfg_file.write_text(json.dumps(initial_data), encoding="utf-8")

            success = sync_agents_runtime.update_openclaw_config_file(cfg_file)
            self.assertTrue(success)

            updated = json.loads(cfg_file.read_text(encoding="utf-8"))
            self.assertEqual(updated["existing_key"], "preserved_val")
            self.assertEqual(updated["agents"]["defaults"]["model"]["primary"], "google/gemini-2.5-flash")
            self.assertIn("groq/llama-3.3-70b-versatile", updated["agents"]["defaults"]["model"]["fallbacks"])
            # Invalid models.providers apiKey dict blocks must be removed for OpenClaw schema validity
            self.assertNotIn("models", updated)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_update_openclaw_config_file_handles_corrupt_json(self) -> None:
        """Test safe handling when openclaw.json has invalid JSON."""
        tmp_dir = Path("tmp_test_corrupt")
        tmp_dir.mkdir(exist_ok=True)
        cfg_file = tmp_dir / "corrupt.json"
        try:
            cfg_file.write_text("invalid json contents", encoding="utf-8")
            success = sync_agents_runtime.update_openclaw_config_file(cfg_file)
            self.assertFalse(success)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_sync_openclaw_workspace(self) -> None:
        """Test copying Mr.Jon SOUL.md and IDENTITY.md to workspace."""
        base_dir = Path("tmp_test_ws")
        deploy_dir = base_dir / "deploy" / "openclaw" / "workspace"
        deploy_dir.mkdir(parents=True, exist_ok=True)
        (deploy_dir / "SOUL.md").write_text("Soul of Mr.Jon", encoding="utf-8")
        (deploy_dir / "IDENTITY.md").write_text("Identity of Mr.Jon", encoding="utf-8")

        ws_dir = base_dir / "workspace" / "oisha"

        try:
            with patch.object(sync_agents_runtime, "OPENCLAW_DEPLOY_DIR", base_dir / "deploy" / "openclaw"):
                success = sync_agents_runtime.sync_openclaw_workspace(ws_dir, owner_user=None)
                self.assertTrue(success)
                self.assertEqual((ws_dir / "SOUL.md").read_text(encoding="utf-8"), "Soul of Mr.Jon")
                self.assertEqual((ws_dir / "IDENTITY.md").read_text(encoding="utf-8"), "Identity of Mr.Jon")
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_sync_all_openclaw_installations(self) -> None:
        """Test discovering and synchronizing all openclaw directories in homes."""
        base_dir = Path("tmp_test_inst")
        fake_home = base_dir / "ubuntu"
        oc_dir = fake_home / ".openclaw"
        oc_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = oc_dir / "openclaw.json"
        cfg_path.write_text("{}", encoding="utf-8")

        try:
            with patch("subprocess.run") as mock_subproc:
                mock_subproc.return_value = MagicMock(returncode=0)
                sync_agents_runtime.sync_all_openclaw_installations(base_homes=[fake_home])
                self.assertTrue(cfg_path.is_file())
                updated = json.loads(cfg_path.read_text(encoding="utf-8"))
                self.assertEqual(updated["agents"]["defaults"]["model"]["primary"], "google/gemini-2.5-flash")
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_sync_hermes_agent_skips_when_missing(self) -> None:
        """Test Hermes sync gracefully skips if /home/hermes/.hermes does not exist."""
        non_existent = Path("tmp_non_existent_hermes")
        sync_agents_runtime.sync_hermes_agent(hermes_dir=non_existent)

    def test_sync_hermes_agent_copies_soul_and_configures(self) -> None:
        """Test Hermes agent sync copies SOUL.md and configures gemini-2.5-flash."""
        base_dir = Path("tmp_test_hermes")
        deploy_hermes = base_dir / "deploy" / "hermes"
        deploy_hermes.mkdir(parents=True, exist_ok=True)
        (deploy_hermes / "SOUL.md").write_text("Oisha SOUL", encoding="utf-8")

        hermes_home = base_dir / "hermes_home"
        hermes_home.mkdir(parents=True, exist_ok=True)

        try:
            with (
                patch.object(sync_agents_runtime, "HERMES_DEPLOY_DIR", deploy_hermes),
                patch("subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                sync_agents_runtime.sync_hermes_agent(hermes_dir=hermes_home)
                self.assertTrue((hermes_home / "SOUL.md").is_file())
                self.assertEqual((hermes_home / "SOUL.md").read_text(encoding="utf-8"), "Oisha SOUL")
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_restart_openclaw_gateway_systemd(self) -> None:
        """Test restarting gateway via systemd when unit is found."""
        with (
            patch("os.name", "posix"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(stdout="openclaw-gateway.service enabled", returncode=0),
                MagicMock(returncode=0),
                MagicMock(stdout="4242 openclaw gateway\n", returncode=0),  # pgrep check
            ]
            sync_agents_runtime.restart_openclaw_gateway()
            self.assertEqual(mock_run.call_count, 3)

    def test_restart_openclaw_gateway_cli_fallback(self) -> None:
        """Test restarting gateway via CLI and background fallback."""
        with (
            patch("os.name", "posix"),
            patch("subprocess.run") as mock_run,
            patch("time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout="", returncode=1),  # unit 1
                MagicMock(stdout="", returncode=1),  # unit 2
                MagicMock(stdout="", returncode=1),  # unit 3
                MagicMock(stdout="restarted", returncode=0),  # cli restart ubuntu
                MagicMock(stdout="12345\n", returncode=0),  # pgrep check
                MagicMock(stdout="Gateway active", returncode=0),  # status check
            ]
            sync_agents_runtime.restart_openclaw_gateway()
            self.assertGreaterEqual(mock_run.call_count, 5)

    def test_main_orchestration(self) -> None:
        """Test main orchestrator executes all steps."""
        with (
            patch.object(sync_agents_runtime, "sync_all_openclaw_installations") as m_oc,
            patch.object(sync_agents_runtime, "sync_hermes_agent") as m_hermes,
            patch.object(sync_agents_runtime, "restart_openclaw_gateway") as m_gw,
        ):
            sync_agents_runtime.main()
            m_oc.assert_called_once()
            m_hermes.assert_called_once()
            m_gw.assert_called_once()


if __name__ == "__main__":
    unittest.main()
