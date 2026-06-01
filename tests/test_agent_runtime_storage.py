from src.services.core.agent_runtime import get_storage_health


def test_remote_storage_health_uses_backend_counts():
    health = get_storage_health(
        "/tmp/local-placeholder.db",
        backend="turso",
        recent_job_runs=[{"job_name": "daily_report"}],
        storage_counts={
            "scheduled_jobs": 4,
            "kv_settings": 3,
            "agent_actions": 6,
            "users": 1,
            "call_analyses": 2,
        },
    )

    assert health["backend"] == "turso"
    assert health["scheduler_rows"] == 4
    assert health["kv_rows"] == 3
    assert health["agent_action_rows"] == 6
    assert health["user_rows"] == 1
    assert health["call_analysis_rows"] == 2
    assert health["recent_job_runs"] == [{"job_name": "daily_report"}]
