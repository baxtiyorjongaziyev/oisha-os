from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.aiogram_cloudrun import AiogramCloudRuntime, create_app
from src.settings import settings


class _Head:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.received = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def receive(self, payload):
        self.received.append(payload)
        return {"ok": True, "duplicate": False, "update_id": payload["update_id"]}

    def health(self):
        return {
            "status": "ok",
            "head": "aiogram_bot_token",
            "ingress": "webhook",
            "userbot_enabled": False,
            "webhook_registered": True,
        }


class _Database:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def test_cloudrun_webhook_enforces_secret_and_owns_lifecycle(monkeypatch):
    head = _Head()
    database = _Database()

    async def runtime_factory():
        return AiogramCloudRuntime(head=head, database=database)

    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", SecretStr("secret-value"))
    app = create_app(runtime_factory=runtime_factory)

    with TestClient(app) as client:
        assert head.started is True
        assert client.get("/healthz").json()["userbot_enabled"] is False
        assert client.post("/telegram/webhook", json={"update_id": 10}).status_code == 403
        response = client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret-value"},
            json={"update_id": 10},
        )
        assert response.status_code == 200
        assert response.json()["update_id"] == 10

    assert head.stopped is True
    assert database.closed is True


def test_cloudrun_artifacts_exclude_userbot_secrets():
    root = Path(__file__).resolve().parents[1]
    app_text = (root / "src" / "aiogram_cloudrun.py").read_text(encoding="utf-8")
    docker_text = (root / "deploy" / "cloud-run-aiogram.Dockerfile").read_text(
        encoding="utf-8"
    )
    deploy_text = (root / "scripts" / "deploy_aiogram_cloudrun.ps1").read_text(
        encoding="utf-8"
    )

    assert "settings.USERBOT_SESSION_STRING" not in app_text
    assert "settings.API_HASH" not in app_text
    assert "settings.API_ID" not in app_text
    for text in (docker_text, deploy_text):
        assert "USERBOT_SESSION_STRING" not in text
        assert "API_HASH" not in text
        assert "API_ID" not in text
    assert "--max-instances 1" in deploy_text
    assert "--min-instances 0" in deploy_text
    assert "--concurrency 1" in deploy_text
    assert "OISHA_ALLOW_GCP" in deploy_text
