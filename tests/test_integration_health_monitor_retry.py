import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "integration_health_monitor.py"
_spec = importlib.util.spec_from_file_location("integration_health_monitor", _PATH)
mon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mon)

SSL_EOF = "AmoCRM: Aloqa uzildi (SSLError: ... UNEXPECTED_EOF_WHILE_READING)"


def _seq(*results):
    it = iter(results)
    calls = []

    def fn():
        calls.append(1)
        return next(it)

    fn.calls = calls
    return fn


def test_transient_ssl_drop_recovers_without_alert():
    fn = _seq((False, SSL_EOF), (True, "AmoCRM: OK"))
    slept = []
    assert mon._run_with_retry(fn, sleep=slept.append) == (True, "AmoCRM: OK")
    assert len(fn.calls) == 2
    assert slept == [5]


def test_persistent_network_failure_still_reported():
    fn = _seq((False, SSL_EOF), (False, SSL_EOF), (False, SSL_EOF))
    slept = []
    ok, detail = mon._run_with_retry(fn, sleep=slept.append)
    assert ok is False and "SSLError" in detail
    assert len(fn.calls) == 3
    assert slept == [5, 15]


def test_real_config_error_is_not_retried():
    fn = _seq((False, "Google Sheets: Kalit fayli topilmadi (data/service_account.json)"))
    slept = []
    ok, _ = mon._run_with_retry(fn, sleep=slept.append)
    assert ok is False
    assert len(fn.calls) == 1
    assert slept == []
