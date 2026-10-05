"""Read-only process liveness probes for userbot ownership."""

import ctypes
import os
import sys
from ctypes import wintypes


def _load_kernel32():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _last_error():
    return ctypes.get_last_error()


def _is_windows_process_dead(pid: int) -> bool:
    kernel = _load_kernel32()
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        # Only ERROR_INVALID_PARAMETER proves the PID does not exist.
        return _last_error() == 87
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0
    finally:
        kernel.CloseHandle(handle)


def is_process_dead(pid: int) -> bool:
    if sys.platform == 'win32':
        return _is_windows_process_dead(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False
