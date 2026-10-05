from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services.core.telegram import process_liveness as probe


@pytest.mark.parametrize('wait_result,expected', [(0, True), (258, False), (0xFFFFFFFF, False)])
def test_windows_probe_closes_handle_without_signalling_process(monkeypatch, wait_result, expected):
    kernel = SimpleNamespace(OpenProcess=Mock(return_value=123),
                             WaitForSingleObject=Mock(return_value=wait_result),
                             CloseHandle=Mock())
    monkeypatch.setattr(probe, '_load_kernel32', lambda: kernel)
    assert probe._is_windows_process_dead(42) is expected
    kernel.OpenProcess.assert_called_once_with(0x00100000, False, 42)
    kernel.WaitForSingleObject.assert_called_once_with(123, 0)
    kernel.CloseHandle.assert_called_once_with(123)


@pytest.mark.parametrize('error,expected', [(87, True), (5, False), (0, False)])
def test_windows_probe_fails_closed_for_unknown_or_denied_process(monkeypatch, error, expected):
    kernel = SimpleNamespace(OpenProcess=Mock(return_value=0),
                             WaitForSingleObject=Mock(), CloseHandle=Mock())
    monkeypatch.setattr(probe, '_load_kernel32', lambda: kernel)
    monkeypatch.setattr(probe, '_last_error', lambda: error)
    assert probe._is_windows_process_dead(42) is expected
    kernel.WaitForSingleObject.assert_not_called()
    kernel.CloseHandle.assert_not_called()


def test_windows_dispatch_never_calls_os_kill(monkeypatch):
    monkeypatch.setattr(probe, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setattr(probe, '_is_windows_process_dead', Mock(return_value=True))
    kill = Mock(side_effect=AssertionError('must not signal Windows process'))
    monkeypatch.setattr(probe.os, 'kill', kill)
    assert probe.is_process_dead(42) is True
    kill.assert_not_called()


@pytest.mark.parametrize('error,expected', [(None, False), (ProcessLookupError(), True), (PermissionError(), False)])
def test_posix_probe_preserves_permission_boundary(monkeypatch, error, expected):
    monkeypatch.setattr(probe, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(probe.os, 'kill', Mock(side_effect=error))
    assert probe.is_process_dead(42) is expected
