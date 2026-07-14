import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))


class DeploymentSecurityTests(unittest.TestCase):
    def test_units_bind_only_loopback(self):
        upstream = (ROOT / "deploy/systemd/telegram-mcp-upstream.service").read_text()
        gateway = (
            ROOT / "deploy/systemd/oisha-telegram-mcp-gateway.service"
        ).read_text()
        self.assertIn("MCP_HOST=127.0.0.1", upstream)
        self.assertIn("TELEGRAM_MCP_GATEWAY_HOST=127.0.0.1", gateway)
        self.assertIn("http://127.0.0.1:8765/mcp", gateway)
        self.assertNotIn("0.0.0.0", upstream + gateway)
        self.assertIn("NoNewPrivileges=true", upstream)
        self.assertIn("NoNewPrivileges=true", gateway)

    def test_upstream_wrapper_rejects_session_reuse(self):
        wrapper = (ROOT / "scripts/run_telegram_mcp_upstream.py").read_text()
        self.assertIn("dedicated == production", wrapper)
        self.assertNotIn("print(dedicated", wrapper)
        self.assertNotIn("print(production", wrapper)


if __name__ == "__main__":
    unittest.main()
