from pathlib import Path


def test_ai_autopilot_requires_explicit_opt_in():
    boot_source = Path("src/boot.py").read_text(encoding="utf-8")

    assert 'os.getenv("ENABLE_AI_AUTOPILOT", "")' in boot_source
    assert 'asyncio.create_task(ai_autopilot_loop(), name="ai_autopilot_loop")' in boot_source

