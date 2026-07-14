from src.scripts import oauth_server


class DummyHTTPServer:
    address = None
    handled = False

    def __init__(self, address, handler_cls):
        type(self).address = address
        self.handler_cls = handler_cls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def handle_request(self):
        type(self).handled = True


def test_oauth_server_binds_to_localhost_by_default(monkeypatch):
    DummyHTTPServer.address = None
    DummyHTTPServer.handled = False
    monkeypatch.delenv("OISHA_OAUTH_BIND_HOST", raising=False)
    monkeypatch.delenv("OISHA_OAUTH_PORT", raising=False)
    monkeypatch.setattr(oauth_server.http.server, "HTTPServer", DummyHTTPServer)

    oauth_server.run_server()

    assert DummyHTTPServer.address == ("127.0.0.1", 9999)
    assert DummyHTTPServer.handled is True


def test_oauth_server_exposes_public_host_only_when_explicit(monkeypatch):
    DummyHTTPServer.address = None
    monkeypatch.setenv("OISHA_OAUTH_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("OISHA_OAUTH_PORT", "10001")
    monkeypatch.setattr(oauth_server.http.server, "HTTPServer", DummyHTTPServer)

    oauth_server.run_server()

    assert DummyHTTPServer.address == ("0.0.0.0", 10001)


def test_oauth_server_falls_back_to_default_port_on_invalid_value(monkeypatch):
    """OISHA_OAUTH_PORT noto'g'ri qiymatga (masalan bo'sh yoki matn)
    o'rnatilgan bo'lsa, server crash bo'lmasdan default portga qaytishi kerak."""
    DummyHTTPServer.address = None
    DummyHTTPServer.handled = False
    monkeypatch.delenv("OISHA_OAUTH_BIND_HOST", raising=False)
    monkeypatch.setenv("OISHA_OAUTH_PORT", "not-a-number")
    monkeypatch.setattr(oauth_server.http.server, "HTTPServer", DummyHTTPServer)

    oauth_server.run_server()

    assert DummyHTTPServer.address == ("127.0.0.1", 9999)
    assert DummyHTTPServer.handled is True
