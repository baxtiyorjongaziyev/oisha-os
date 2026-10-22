"""Synthetic request addresses; no production network or employee data."""
from types import SimpleNamespace

import pytest
from src.services.core.attendance.network import client_ip


def request(peer, **headers):
    return SimpleNamespace(client=SimpleNamespace(host=peer) if peer else None, headers=headers)


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_local_proxy_uses_real_ip(peer):
    assert client_ip(request(peer, **{"X-Real-IP": "8.8.8.8", "X-Forwarded-For": "1.1.1.1"})) == "8.8.8.8"


def test_untrusted_peer_cannot_spoof_office_ip():
    assert client_ip(request("1.1.1.1", **{"X-Real-IP": "8.8.8.8"})) == "1.1.1.1"


def test_forwarded_chain_uses_last_hop():
    assert client_ip(request("127.0.0.1", **{"X-Forwarded-For": "1.1.1.1, 8.8.8.8"})) == "8.8.8.8"


@pytest.mark.parametrize("candidate", ["", "127.0.0.1", "10.0.0.1", "invalid", "8.8.8.8, 1.1.1.1"])
def test_unknown_or_nonpublic_address_fails_closed(candidate):
    assert client_ip(request("127.0.0.1", **{"X-Real-IP": candidate})) is None


def test_missing_peer_ignores_headers():
    assert client_ip(request(None, **{"X-Real-IP": "8.8.8.8"})) is None
