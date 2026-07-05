import os
from unittest.mock import patch

from src.services.core.agent_runtime import detect_runtime_source


def test_explicit_oracle_runtime_overrides_cloud_flag():
    with patch.dict(
        os.environ,
        {"OISHA_RUNTIME": "vm_service", "RUNNING_IN_CLOUD": "1"},
    ):
        assert detect_runtime_source() == "vm_service"


def test_systemd_runtime_overrides_cloud_flag():
    with patch.dict(
        os.environ,
        {"SYSTEMD_EXEC_PID": "1234", "RUNNING_IN_CLOUD": "1"},
        clear=True,
    ):
        assert detect_runtime_source() == "vm_service"
