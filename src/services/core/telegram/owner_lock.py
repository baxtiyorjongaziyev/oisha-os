"""Atomic ownership statements and local process checks."""

import os
import socket
from typing import Optional


_OWNER_INSERT_SQL = """
INSERT INTO oauth_tokens (service_name, access_token, refresh_token, expires_at, updated_at, extra_data)
VALUES (?, ?, 'n/a', ?, ?, NULL)
ON CONFLICT(service_name) DO NOTHING
"""

_OWNER_RELEASE_SQL = """
UPDATE oauth_tokens
   SET access_token = '', expires_at = ?, updated_at = ?
 WHERE service_name = ? AND access_token = ?
"""


# Shu hostdagi o'lgan jarayon qoldirgan egalikni olish. `access_token = ?`
# sharti atomiklikni saqlaydi: ikki yangi instance bir vaqtda urinsa, faqat
# birinchisi o'lik egani almashtiradi, ikkinchisining UPDATE'i hech narsa
# topmaydi.
_OWNER_TAKEOVER_SQL = """
UPDATE oauth_tokens
   SET access_token = ?, expires_at = ?, updated_at = ?
 WHERE service_name = ? AND access_token = ?
"""


def _is_dead_local_holder(holder: Optional[str]) -> bool:
    """Ega shu hostdagi, endi mavjud bo'lmagan jarayonmi?

    systemd restart'da eski jarayon heartbeat TTL tugamasdan o'ladi; uning
    yozuvi yangi jarayonni 'boshqa instance tirik' deb userbot'siz qoldirardi.
    O'lgan jarayon Telegram ulanishini ushlab turolmaydi — xavfsiz olinadi.
    """
    host, _, pid = (holder or "").rpartition(":")
    if host != socket.gethostname() or not pid.isdigit() or int(pid) == os.getpid():
        return False
    from src.services.core.telegram.process_liveness import is_process_dead

    return is_process_dead(int(pid))


