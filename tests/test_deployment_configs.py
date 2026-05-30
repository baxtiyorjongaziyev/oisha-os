import os
import pytest


def test_systemd_service_files_exist_and_valid():
    oisha_path = "ops/oisha.service"
    watchdog_path = "ops/watchdog.service"

    assert os.path.exists(oisha_path), "ops/oisha.service does not exist!"
    assert os.path.exists(watchdog_path), "ops/watchdog.service does not exist!"

    # 1. Validate oisha.service structure
    with open(oisha_path, "r", encoding="utf-8") as f:
        oisha_content = f.read()
    
    assert "[Unit]" in oisha_content
    assert "[Service]" in oisha_content
    assert "[Install]" in oisha_content
    assert "WorkingDirectory=" in oisha_content
    assert "ExecStart=" in oisha_content
    assert "Restart=always" in oisha_content
    assert "Environment=PYTHONPATH=" in oisha_content

    # 2. Validate watchdog.service structure
    with open(watchdog_path, "r", encoding="utf-8") as f:
        watchdog_content = f.read()

    assert "[Unit]" in watchdog_content
    assert "[Service]" in watchdog_content
    assert "[Install]" in watchdog_content
    assert "WorkingDirectory=" in watchdog_content
    assert "ExecStart=" in watchdog_content
    assert "Restart=always" in watchdog_content


def test_deploy_script_exists_and_executable_logic():
    deploy_path = "scripts/deploy_oracle.sh"
    assert os.path.exists(deploy_path), "scripts/deploy_oracle.sh does not exist!"

    with open(deploy_path, "r", encoding="utf-8") as f:
        deploy_content = f.read()

    # Verify key automation logic inside deploy_oracle.sh
    assert "PROJECT_DIR=" in deploy_content
    assert "apt-get install" in deploy_content
    assert "systemctl daemon-reload" in deploy_content
    assert "systemctl enable oisha" in deploy_content
    assert "systemctl restart oisha" in deploy_content
    assert "sed" in deploy_content  # Dynamic path replacement logic
