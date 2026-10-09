"""The generated Cloudflare Worker must never inline the Workers AI token."""
from __future__ import annotations

from pydantic import SecretStr

from src.services.edge import edge_personalizer as ep


def test_worker_script_does_not_embed_api_token(monkeypatch):
    token = "cf-secret-token-should-not-leak-1234567890"
    monkeypatch.setattr(ep.settings, "CLOUDFLARE_ACCOUNT_ID", "acc123", raising=False)
    monkeypatch.setattr(ep.settings, "CLOUDFLARE_AI_API_TOKEN", SecretStr(token), raising=False)

    script = ep.EdgePersonalizer().build_worker_script()

    assert token not in script
    assert "env.CLOUDFLARE_AI_API_TOKEN" in script
