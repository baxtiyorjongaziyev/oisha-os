"""Guards against daemon loops being defined but never scheduled.

brain_evolution_loop and hisobchi_gap_report_loop both existed as fully
implemented coroutines with no asyncio.create_task call site anywhere in the
repo -- they silently never ran. This test asserts the wiring exists in
boot_application's source so a future refactor can't silently drop it again
without a real coroutine to import and await.
"""
from pathlib import Path

BOOT_SOURCE = Path("src/bootstrap/orchestration/boot.py").read_text(encoding="utf-8")


def test_brain_evolution_loop_is_scheduled():
    assert "_brain_evolution_loop" in BOOT_SOURCE
    assert 'asyncio.create_task(_brain_evolution_loop()' in BOOT_SOURCE


def test_hisobchi_gap_report_loop_is_scheduled():
    assert "hisobchi_gap_report_loop" in BOOT_SOURCE
    assert "asyncio.create_task(\n        hisobchi_gap_report_loop(" in BOOT_SOURCE


def test_brain_evolution_loop_uses_a_real_oisha_brain_instance():
    daemon_tasks_source = Path("src/entrypoint/daemon_tasks.py").read_text(
        encoding="utf-8"
    )
    assert "from src.services.core.agent_brain import oisha_brain" in daemon_tasks_source
    assert "or oisha_brain" in daemon_tasks_source
