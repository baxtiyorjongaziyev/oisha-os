from __future__ import annotations

import json
from pathlib import Path

from src.services.core.ai_agent_orchestrator import (
    CANONICAL_AGENT_BLUEPRINTS,
    evaluate_fleet_status,
    fire_ai_agent,
    hire_ai_agent,
    revive_or_cleanup_fleet,
)


def _sample_jobs() -> list[dict]:
    return [
        {
            "id": "3375a5b1e741",
            "name": "ertalab-davomat-10-00",
            "enabled": True,
            "schedule": {"kind": "cron", "expr": "0 10 * * 1-6"},
            "deliver": "telegram:-1003114662117",
            "last_status": "ok",
            "last_error": None,
        },
        {
            "id": "883372a46b8d",
            "name": "ertalab-standup",
            "enabled": True,
            "schedule": {"kind": "cron", "expr": "0 9 * * *"},
            "deliver": "telegram:-1003114662117",
            "last_status": "ok",
            "last_error": None,
        },
        {
            "id": "cd8ca81f9e75",
            "name": "Ertaga 29-oktabr Azizullo",
            "enabled": True,
            "schedule": {"kind": "cron", "expr": "0 9 * * *"},
            "deliver": "origin",
            "last_status": "error",
            "last_error": "origin_unavailable",
        },
    ]


def test_evaluate_fleet_detects_zombies_and_missing_blueprints(tmp_path: Path):
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": _sample_jobs()}), encoding="utf-8")

    res = evaluate_fleet_status(jobs_path=str(jobs_file), db_path=str(tmp_path / "missing.db"))
    assert res["success"] is True
    assert res["summary"]["optimal_team_size"] == len(CANONICAL_AGENT_BLUEPRINTS)
    # ertalab-standup (duplicate) and Ertaga 29-oktabr (origin ad-hoc) should be flagged as zombie
    zombie_names = {z["name"] for z in res["zombie_or_duplicate_agents"]}
    assert "ertalab-standup" in zombie_names
    assert "Ertaga 29-oktabr Azizullo" in zombie_names

    rec_slugs = {r["slug"] for r in res["recommended_hires"]}
    assert "ai_hr_evening_18" in rec_slugs
    assert "ai_debitor_finance" in rec_slugs


def test_hire_and_fire_ai_agent(tmp_path: Path):
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": []}), encoding="utf-8")

    hired = hire_ai_agent(blueprint_slug="ai_hr_evening_18", jobs_path=str(jobs_file))
    assert hired["success"] is True
    assert hired["action"] == "hired_new_agent"
    assert hired["agent"]["name"] == "kechki-sarhisob-18-00"

    status = evaluate_fleet_status(jobs_path=str(jobs_file), db_path=str(tmp_path / "missing.db"))
    rec_slugs = {r["slug"] for r in status["recommended_hires"]}
    assert "ai_hr_evening_18" not in rec_slugs

    fired = fire_ai_agent("kechki-sarhisob-18-00", jobs_path=str(jobs_file))
    assert fired["success"] is True
    assert fired["action"] == "disabled"


def test_revive_or_cleanup_fleet_disables_zombies_and_hires_core(tmp_path: Path):
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": _sample_jobs()}), encoding="utf-8")

    res = revive_or_cleanup_fleet(
        auto_fire_zombies=True,
        auto_hire_missing_core=True,
        jobs_path=str(jobs_file),
        db_path=str(tmp_path / "missing.db"),
    )
    assert res["success"] is True
    assert len(res["fired_zombie_agents"]) == 2
    assert res["fleet_status"]["zombie_or_duplicate_count"] == 0
    assert res["fleet_status"]["recommended_new_hires_count"] == 0
