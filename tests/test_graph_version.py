from src.services.core.instagram.graph_version import (
    DEFAULT_GRAPH_API_VERSION,
    graph_api_version,
    graph_base,
)


def test_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("META_GRAPH_API_VERSION", raising=False)
    assert graph_api_version() == DEFAULT_GRAPH_API_VERSION == "v25.0"
    assert graph_base() == "https://graph.facebook.com/v25.0"


def test_env_override_is_trimmed(monkeypatch):
    monkeypatch.setenv("META_GRAPH_API_VERSION", "  v26.0 ")
    assert graph_base() == "https://graph.facebook.com/v26.0"


def test_blank_env_falls_back(monkeypatch):
    monkeypatch.setenv("META_GRAPH_API_VERSION", "   ")
    assert graph_api_version() == DEFAULT_GRAPH_API_VERSION
