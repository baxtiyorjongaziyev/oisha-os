"""Context and Session Engine for Hermes Agent in Oisha-OS.

Provides multi-turn session lineage tracking and dynamic context assembly
for sales staff coaching, Baxtiyorjon Gaziyev DMs, and branding consultations.
"""
from __future__ import annotations

import logging
import time
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("HermesContext")


class HermesSessionStore:
    """SQLite-backed session tracker for multi-turn Hermes interactions."""

    def __init__(self, ttl_seconds: float = 86400.0, db_path: str = "data/hermes_sessions.db"):
        # Maps (channel, entity_id) -> (session_id, last_accessed_timestamp)
        self._sessions: Dict[Tuple[str, str], Tuple[str, float]] = {}
        self.ttl_seconds = ttl_seconds
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (channel TEXT, entity TEXT, session TEXT, accessed REAL, PRIMARY KEY(channel, entity))")

    def get_session(self, channel: str, entity_id: str) -> Optional[str]:
        """Retrieve active session_id if within TTL."""
        key = (channel, str(entity_id))
        with sqlite3.connect(self.db_path) as db:
            entry = db.execute("SELECT session, accessed FROM sessions WHERE channel=? AND entity=?", key).fetchone()
        if not entry:
            return None

        sess_id, last_ts = entry
        if time.time() - last_ts > self.ttl_seconds:
            # Expired session
            self.clear_session(channel, entity_id)
            return None

        # Update access timestamp
        self.set_session(channel, entity_id, sess_id)
        return sess_id

    def set_session(self, channel: str, entity_id: str, session_id: str) -> None:
        """Register or update active session_id."""
        if not session_id:
            return
        key = (channel, str(entity_id))
        self._sessions[key] = (session_id.strip(), time.time())
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)", (*key, session_id.strip(), time.time()))
        logger.debug("[HERMES-SESSION] Bound (%s, %s) -> %s", channel, entity_id, session_id)

    def clear_session(self, channel: str, entity_id: str) -> None:
        """Clear session for entity."""
        key = (channel, str(entity_id))
        self._sessions.pop(key, None)
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM sessions WHERE channel=? AND entity=?", key)

    def total_active_sessions(self) -> int:
        """Count active non-expired sessions."""
        with sqlite3.connect(self.db_path) as db:
            return db.execute("SELECT count(*) FROM sessions WHERE accessed>=?", (time.time() - self.ttl_seconds,)).fetchone()[0]


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
            f"Sen — {cls.FOUNDER_NAME}san ({cls.AGENCY_NAME} agentligi asoschisi va bosh art-direktori).\n"
            f"Identitet: Allohning quli -> branding eksperti -> Jon Branding agentligi egasi -> tadbirkor.\n"
            f"Falsafa: Tizimli fikrlash, aniq mezonlar va pragmatizm. Bekorchi vaqt sarfini yoqtirmaysan.\n\n"
            f"Vazifa: Mijoz yoki hamkorga shaxsan o'z nomingdan juda samimiy, xushmuomala, lo'nda va tabiiy javob yoz.\n\n"
            f"QAT'IY QOIDALAR VA INVARIANTLAR:\n"
            f"1. O'zingni hech qachon 'bot', 'AI' yoki 'assistent' deb tanishtirma. 1-shaxsda gapir ('men', 'biz').\n"
            f"2. Muloqot ohangi: Qisqa, amaliy, ortiqcha lutf-xushomadsiz, tadbirkorona samimiy o'zbek tilida.\n"
            f"3. Narx so'ralganda: Darhol quruq narx aytib qochirma. Jon Branding xizmatlari zanjiri: "
            f"Naming -> Logotip & Firma uslubi -> Qadoq dizayni -> Tovar belgisini patentlash. "
            f"Avval soha va ko'lamni bilish uchun qisqa brif tashla yoki 15 daqiqalik uchrashuvga chaqir.\n"
            f"4. Qadriyatlar filtri: Shar'iy shubhali, islomga zid, nojoiz yoki boykot qilingan loyihalarni "
            f"muloyim va qat'iy rad et.\n"
            f"5. Hozir uchrashuvda yoki ijodiy jarayonda bo'lsang, buni samimiy aytib, tez orada batafsil "
            f"javob yozishingni bildir.\n"
            f"6. Hech qanday asossiz uydirma narx yoki yolg'on va'da berma. Matn ko'pi bilan 2-3 jumlada tugasin."
        )

    @classmethod
    def build_clone_decision_prompt(cls) -> str:
        """Build decision framework prompt for Baxtiyorjon's Autonomous AI Clone."""
        return (
            f"Sen — {cls.FOUNDER_NAME}ning Digital Twin (Raqamli Kloni)san.\n"
            f"Vazifang — kiruvchi har bir xabarni Baxtiyorjonning 3 yillik tajribasi, qarorlari va "
            f"prinsiplari asosida tahlil qilib, optimal qaror va javob loyihasini chiqarishdir.\n\n"
            f"QAROR ZONALARI:\n"
            f"- YASHIL (Avtonom): Brifing berish, portfolioni ulashish, uchrashuv belgilash, xodimlar bilan soatlik nazorat.\n"
            f"- SARIQ (Tavsiya + Hisobot): Standart chegirma chegarasi (max 10%), muddatni 2-3 kunga surish.\n"
            f"- QIZIL (Inson tasdig'i): To'lovlarni qaytarish, shartnomani bekor qilish, moliyaviy majburiyat.\n\n"
            f"Dizayn didi: Minimal, premium, zamonaviy, clean, luxury. O'ynoqi va pala-partish uslub yoqmaydi.\n"
            f"Chiqish: Qaror asosi + 1-shaxsda Baxtiyorjon nomidan yozilgan aniq, qisqa javob matni."
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


    @classmethod
    def get_owner_philosophy_summary(cls) -> Dict[str, str]:
        """Summary of founder values, decision policies, and communication rules."""
        return {
            "identity": "Allohning quli -> branding expert -> Jon Branding egasi -> tadbirkor",
            "communication_style": "Qisqa, lo'nda, samimiy, pragmatik, tadbirkorona o'zbek tilida",
            "design_taste": "Minimal, premium, zamonaviy, clean, luxury",
            "decision_rule": "Avval brifing yoki 15 daqiqalik diagnostika uchrashuvi; asossiz narx aytilmaydi",
            "forbidden": "Shar'iy shubhali, islomga zid, harom yoki boykot qilingan brendlar loyihasi",
        }


_GLOBAL_SESSION_STORE: Optional[HermesSessionStore] = None


def get_hermes_session_store() -> HermesSessionStore:
    """Get singleton HermesSessionStore instance."""
    global _GLOBAL_SESSION_STORE
    if _GLOBAL_SESSION_STORE is None:
        _GLOBAL_SESSION_STORE = HermesSessionStore()
    return _GLOBAL_SESSION_STORE
