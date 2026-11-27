"""Bounded, cancellation-safe locks shared by bridge and CLI on one host.

All writers must share OISHA_DATA_DIR (and OS access to that directory).
Lock files must never be unlinked while writers run: their inode is the lock.
Multi-host deployments need a distributed lock before enabling merge writers.
"""
from __future__ import annotations

import asyncio
import errno
import os
from contextlib import asynccontextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_STRIPES = 256


def _try_lock(fd: int) -> bool:
    try:
        if os.name == "nt":
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            raise
        return False


@asynccontextmanager
async def lead_locks(*lead_ids: int, directory: Path | None = None):
    """Hold ordered stripe locks through the entire read/modify/write sequence.

    OS locks also serialize tasks in this process via separate file handles.
    Errors fail closed; process exit closes descriptors and releases the locks.
    """
    if directory is None:
        base = Path(os.environ.get("OISHA_DATA_DIR") or Path(__file__).resolve().parents[5] / "data")
        directory = base / "tg-amo-merge-locks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptors = []
    try:
        for stripe in sorted({int(lead_id) % _STRIPES for lead_id in lead_ids}):
            fd = os.open(directory / f"{stripe}.lock", os.O_RDWR | os.O_CREAT, 0o600)
            descriptors.append(fd)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            while not _try_lock(fd):
                await asyncio.sleep(0.05)
        yield
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
