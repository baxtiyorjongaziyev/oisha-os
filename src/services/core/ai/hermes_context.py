"""Context and Session Engine for Hermes Agent in Oisha-OS.

Provides multi-turn session lineage tracking and dynamic context assembly
for sales staff coaching, Baxtiyorjon Gaziyev DMs, and branding consultations.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger("HermesContext")


class HermesSessionStore:
    """In-memory thread-safe session tracker for multi-turn Hermes interactions."""

    def __init__(self, ttl_seconds: float = 86400.0):
        # Maps (channel, entity_id) -> (session_id, last_accessed_timestamp)
        self._sessions: Dict[Tuple[str, str], Tuple[str, float]] = {}
        self.ttl_seconds = ttl_seconds

    def get_session(self, channel: str, entity_id: str) -> Optional[str]:
        """Retrieve active session_id if within TTL."""
        key = (channel, str(entity_id))
        entry = self._sessions.get(key)
        if not entry:
            return None

        sess_id, last_ts = entry
        if time.time() - last_ts > self.ttl_seconds:
            # Expired session
            del self._sessions[key]
            return None

        # Update access timestamp
        self._sessions[key] = (sess_id, time.time())
        return sess_id

    def set_session(self, channel: str, entity_id: str, session_id: str) -> None:
        """Register or update active session_id."""
        if not session_id:
            return
        key = (channel, str(entity_id))
        self._sessions[key] = (session_id.strip(), time.time())
        logger.debug("[HERMES-SESSION] Bound (%s, %s) -> %s", channel, entity_id, session_id)

    def clear_session(self, channel: str, entity_id: str) -> None:
        """Clear session for entity."""
        key = (channel, str(entity_id))
        self._sessions.pop(key, None)

    def total_active_sessions(self) -> int:
        """Count active non-expired sessions."""
        now = time.time()
        return sum(
            1 for _, last_ts in self._sessions.values() if now - last_ts <= self.ttl_seconds
        )


class HermesContextEngine:
    """Assembles personas and dynamic business context for Hermes Agent."""

    AGENCY_NAME = "Jon Branding"
    FOUNDER_NAME = "Baxtiyorjon Gaziyev"

    @classmethod
    def build_copilot_system_prompt(cls, staff_name: str = "Rayxon") -> str:
        """Build persona instruction for mentoring sales representatives."""
        return (
            f"Sen — Jon Branding agentligining bosh sotuv murabbiyi va Oisha-OS Copilotisan. "
            f"Sening maqsading — sotuv menejeri {staff_name}ga (@{staff_name}Jonbranding) qo'ng'iroqlar, "
            f"e'tirozlar (narx qimmat, o'ylab ko'raman, bitim cho'zilishi) va mijozlar bilan muloqotda "
            f"yordam berish, aniq psixologik skriptlar va ilhomlantiruvchi yechimlar berishdir.\n\n"
            f"QAT'IY QOIDALAR:\n"
            f"1. Samimiy, professional va do'stona bo'l. {staff_name}ning muvaffaqiyatiga ishonch bildir.\n"
            f"2. Quruq nazariya emas, aynan mijozga aytiladigan tayyor 1-2 ta jonli gap (skript) ber.\n"
            f"3. Jon Branding prinsiplari: sifat, strategiya va mijoz biznesiga uzoq muddatli foyda.\n"
            f"4. Javobni Telegram xabari formatida, ixcham va o'qishga qulay qilib yoz."
        )

    @classmethod
    def build_dm_responder_system_prompt(cls) -> str:
        """Build authentic personal persona for Baxtiyorjon Gaziyev's Telegram DMs."""
        return (
            f"Sen — {cls.FOUNDER_NAME}san ({cls.AGENCY_NAME} agentligi asoschisi va bosh art-direktori). "
            f"Mijoz senga Telegram shaxsiy xabaringga yozgan. Sen 15 daqiqadan beri uchrashuvda yoki "
            f"ijodiy jarayonda bo'lganing sababli darhol javob bera olmading.\n\n"
            f"Vazifa: Mijozga shaxsan o'z nomingdan juda samimiy, xushmuomala va tabiiy javob yoz.\n\n"
            f"QAT'IY INVARIANTLAR:\n"
            f"1. O'zingni hech qachon 'bot', 'AI' yoki 'assistent' deb tanishtirma. 1-shaxsda gapir ('men', 'biz').\n"
            f"2. Hozir biroz band ekanligingni (uchrashuvda ekanligingni) samimiy bildir.\n"
            f"3. Mijozning xabariga qisqa e'tibor qaratib, tez orada shaxsan o'zing batafsil yozishingni ayt.\n"
            f"4. Hech qanday uydirma narx yoki asossiz va'da berma.\n"
            f"5. Matn qisqa va lo'nda bo'lsin (ko'pi bilan 2-3 jumla)."
        )

    @classmethod
    def build_branding_consultant_prompt(cls) -> str:
        """Build persona instruction for inbound branding inquiries."""
        return (
            f"Sen — {cls.AGENCY_NAME} agentligining yetakchi brending va marketing maslahatchisisan. "
            f"Jon Branding xizmatlari: brend strategiyasi, nomlash (naming), logotip, qadoq dizayni, "
            f"patentlash va sotuv tizimlarini avtomatlashtirish.\n\n"
            f"QOIDALAR:\n"
            f"1. Har bir loyiha individual: narxlar loyihaning aniq ko'lami va talablariga qarab shakllantiriladi.\n"
            f"2. Mijoz biznesining ehtiyojini aniqlovchi ochiq savollar ber.\n"
            f"3. Samimiy, professional va nufuzli ohangda muloqot qil."
        )


_GLOBAL_SESSION_STORE: Optional[HermesSessionStore] = None


def get_hermes_session_store() -> HermesSessionStore:
    """Get singleton HermesSessionStore instance."""
    global _GLOBAL_SESSION_STORE
    if _GLOBAL_SESSION_STORE is None:
        _GLOBAL_SESSION_STORE = HermesSessionStore()
    return _GLOBAL_SESSION_STORE
