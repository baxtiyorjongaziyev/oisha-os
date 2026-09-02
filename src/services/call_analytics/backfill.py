from typing import Any, Dict, List, Optional
import structlog
import requests as _requests
from src.time_utils import get_local_now
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallBackfillMixin:
    async def _read_state(self, key: str, default: str = "") -> str:
        get_state = getattr(self.db, "get_state", None) if self.db else None
        if not callable(get_state):
            return default
        try:
            return str(await _maybe_await(get_state(key, default)) or default)
        except Exception as exc:
            logger.warning("[BACKFILL] '%s' holatini o'qib bo'lmadi: %s", key, exc)
            return default

    async def _write_state(self, key: str, value: str) -> None:
        set_state = getattr(self.db, "set_state", None) if self.db else None
        if not callable(set_state):
            return
        try:
            await _maybe_await(set_state(key, value))
        except Exception as exc:
            logger.warning("[BACKFILL] '%s' holatini yozib bo'lmadi: %s", key, exc)

    async def _fetch_leads_page(
        self, page: int, per_page: int = 250
    ) -> Optional[List[Dict[str, Any]]]:
        """Bitimlarning bitta sahifasi.

        `get_leads_detailed` 50 ta bilan cheklangan va sahifalashni
        qo'llab-quvvatlamaydi — u har doim BIRINCHI sahifani qaytaradi,
        shuning uchun tarixga chuqur kirish uchun yaramaydi.

        Qaytaradi:
            `[]`   — sahifa haqiqatan bo'sh, ya'ni TARIX TUGADI;
            `None` — so'rov YIQILDI (401/429/5xx, tarmoq, buzuq JSON).

        Bu farq muhim: xatoni bo'sh sahifa deb hisoblasak, backfill
        "tarix tugadi" deb yolg'on xulosa chiqaradi, kursorni 1-sahifaga
        qaytaradi va tarixning qolgan qismiga hech qachon yetib bormaydi.
        """
        url = f"{self.amocrm.base_url}/api/v4/leads"
        params = {"limit": max(1, min(int(per_page), 250)), "page": int(page), "with": "contacts"}
        try:
            response = await _maybe_await(
                self.amocrm._request_with_auth(
                    _requests.get, url, params=params, timeout=30
                )
            )
        except Exception as exc:
            logger.error("[BACKFILL] %s-sahifa so'rovi yiqildi: %s", page, exc)
            return None

        status = getattr(response, "status_code", 0)
        if status == 204:
            return []
        if status != 200:
            logger.error("[BACKFILL] %s-sahifa HTTP %s", page, status)
            return None
        try:
            return (response.json().get("_embedded") or {}).get("leads") or []
        except Exception as exc:
            logger.error("[BACKFILL] %s-sahifa JSON xatosi: %s", page, exc)
            return None

    async def backfill_call_recordings(
        self,
        limit: int = 50,
        *,
        write: bool = True,
        include_transcript: bool = True,
        max_pages_per_run: int = 20,
        min_call_duration_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Eski qo'ng'iroq yozuvlarini tahlil qiladi (tarixiy backfill).

        `analyze_recent_calls` faqat eng oxirgi bitimlarni ko'radi. Bu esa
        tarix bo'ylab SAHIFAMA-SAHIFA yuradi va qayerda to'xtaganini
        bazada saqlaydi, ya'ni bir necha marta ishga tushirilsa tarixni
        bosqichma-bosqich yopadi.

        Chegara — Gemini kvotasi: `limit` shu YUGURISHDA tahlil qilinadigan
        maksimal qo'ng'iroq soni. Kvota tugasa, sikl darhol to'xtaydi va
        joriy sahifa saqlanadi — keyingi yugurish o'sha yerdan davom etadi.

        Takroriy tahlil bo'lmaydi: `_is_call_processed` va AmoCRM notasidagi
        marker allaqachon tahlil qilingan qo'ng'iroqni o'tkazib yuboradi.

        `min_call_duration_seconds=None` (standart) — sozlamadagi
        `AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS` ishlatiladi, xuddi
        webhook yo'lidagidek. Aks holda backfill avtojavob, band signali
        va boshqa qisqa yozuvlarni ham tahlil qilib, uydirma natijalarni
        bazaga yozib qo'yardi va konversiya raqamlarini buzardi.
        Ataylab hammasini olish kerak bo'lsa — ochiq `0` beriladi.
        """
        await self._load_persisted_cooldown()
        if min_call_duration_seconds is None:
            try:
                from src.settings import settings as _settings

                min_call_duration_seconds = int(
                    getattr(_settings, "AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS", 10)
                )
            except Exception:
                min_call_duration_seconds = 10
        min_call_duration_seconds = max(0, int(min_call_duration_seconds))
        stats: Dict[str, Any] = {
            "leads_scanned": 0,
            "calls_processed": 0,
            "pages_read": 0,
            "start_page": 1,
            "next_page": 1,
            "completed": False,
            "stopped_reason": "",
        }

        if self._defer_calls_without_fallback():
            stats["stopped_reason"] = "gemini_quota_cooldown"
            logger.info(
                "[BACKFILL] Gemini kvotasi sovutishda (%ss) — backfill kechiktirildi.",
                self._gemini_cooldown_remaining(),
            )
            return stats

        try:
            page = max(1, int(await self._read_state(self._BACKFILL_PAGE_KEY, "1") or 1))
        except (TypeError, ValueError):
            page = 1
        stats["start_page"] = page
        stats["next_page"] = page

        target = max(1, int(limit))
        for _ in range(max(1, int(max_pages_per_run))):
            if stats["calls_processed"] >= target:
                stats["stopped_reason"] = "limit_reached"
                break
            if self._defer_calls_without_fallback():
                stats["stopped_reason"] = "gemini_quota_cooldown"
                break

            leads = await self._fetch_leads_page(page)
            stats["pages_read"] += 1
            if leads is None:
                # So'rov yiqildi — bu TARIX TUGADI degani EMAS. Kursor
                # joyida qoladi, `completed` yoqilmaydi: keyingi yugurish
                # aynan shu sahifadan qayta urinadi.
                stats["stopped_reason"] = "page_fetch_failed"
                stats["failed_page"] = page
                break
            if not leads:
                # Tarix tugadi — keyingi yugurish boshidan boshlanadi va
                # oradan qo'shilgan yangi bitimlarni ham qamrab oladi.
                stats["completed"] = True
                stats["stopped_reason"] = stats["stopped_reason"] or "history_exhausted"
                page = 1
                await self._write_state(self._BACKFILL_DONE_KEY, get_local_now().isoformat())
                break

            for lead in leads:
                if stats["calls_processed"] >= target:
                    stats["stopped_reason"] = "limit_reached"
                    break
                if self._defer_calls_without_fallback():
                    stats["stopped_reason"] = "gemini_quota_cooldown"
                    break
                lead_id = lead.get("id")
                if not lead_id:
                    continue
                stats["leads_scanned"] += 1
                try:
                    stats["calls_processed"] += await self.process_call_recordings_for_lead(
                        int(lead_id),
                        caller_phone=self._extract_lead_phone(lead),
                        responsible_user_id=lead.get("responsible_user_id"),
                        write=write,
                        include_transcript=include_transcript,
                        min_call_duration_seconds=min_call_duration_seconds,
                        # Qolgan kvota — bitta bitimda o'nlab yozuv bo'lishi
                        # mumkin, cheklovsiz `limit` osonlik bilan oshib
                        # ketardi va Gemini kvotasini yeb qo'yardi.
                        max_calls_per_lead=max(1, target - stats["calls_processed"]),
                    )
                except Exception as exc:
                    # Bitta bitim yiqilsa butun backfill to'xtamasligi kerak.
                    logger.error("[BACKFILL] lead_id=%s yiqildi: %s", lead_id, exc)

            if stats["stopped_reason"] in {
                "limit_reached",
                "gemini_quota_cooldown",
                "page_fetch_failed",
            }:
                break
            page += 1

        stats["next_page"] = page
        await self._write_state(self._BACKFILL_PAGE_KEY, str(page))
        logger.info("[BACKFILL] Yakun: %s", stats)
        return stats

    async def analyze_recent_contact_calls(
        self,
        limit: int = 50,
        write: bool = True,
        include_transcript: bool = True,
        min_call_duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Analyze contact-level recordings only when they map to one linked lead."""
        await self._load_persisted_cooldown()
        getter = getattr(self.amocrm, "get_recent_contact_call_notes", None)
        linked_leads_getter = getattr(self.amocrm, "get_contact_linked_leads", None)
        if not callable(getter) or not callable(linked_leads_getter):
            return {
                "contact_calls_discovered": 0,
                "contact_calls_resolved": 0,
                "contact_calls_unlinked": 0,
                "contact_calls_ambiguous": 0,
                "contact_calls_processed": 0,
            }

        notes = await _maybe_await(getter(limit=limit))
        stats = {
            "contact_calls_discovered": len(notes or []),
            "contact_calls_resolved": 0,
            "contact_calls_unlinked": 0,
            "contact_calls_ambiguous": 0,
            "contact_calls_processed": 0,
        }
        for note in notes or []:
            if self._defer_calls_without_fallback():
                logger.info(
                    "[CALL] Gemini quota cooldown active; deferring remaining contact recordings."
                )
                break
            if not self._find_audio_url(note.get("params") or {}):
                continue
            contact_id = note.get("entity_id")
            if not contact_id:
                stats["contact_calls_unlinked"] += 1
                continue
            linked_leads = await _maybe_await(linked_leads_getter(int(contact_id)))
            if len(linked_leads) != 1:
                key = (
                    "contact_calls_unlinked"
                    if not linked_leads
                    else "contact_calls_ambiguous"
                )
                stats[key] += 1
                continue
            lead = linked_leads[0]
            lead_id = lead.get("id")
            if not lead_id:
                stats["contact_calls_unlinked"] += 1
                continue
            stats["contact_calls_resolved"] += 1
            stats["contact_calls_processed"] += await self.process_call_recordings_for_lead(
                int(lead_id),
                caller_phone=self._extract_phone_from_note(note),
                responsible_user_id=lead.get("responsible_user_id")
                or note.get("responsible_user_id"),
                write=write,
                include_transcript=include_transcript,
                max_calls_per_lead=1,
                min_call_duration_seconds=min_call_duration_seconds,
                call_notes_override=[note],
            )
        return stats

    async def analyze_recent_calls(
        self,
        limit: int = 20,
        write: bool = True,
        include_transcript: bool = True,
        one_analysis_per_lead: bool = False,
        max_calls_per_lead: int = 0,
        min_call_duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Scan recent AmoCRM leads and analyze their attached call recordings."""
        await self._load_persisted_cooldown()
        if self._defer_calls_without_fallback():
            logger.info(
                "[CALL] Gemini quota cooldown active; deferring recording scan for %ss.",
                self._gemini_cooldown_remaining(),
            )
            return {
                "leads_scanned": 0,
                "calls_processed": 0,
                "contact_calls_discovered": 0,
                "contact_calls_resolved": 0,
                "contact_calls_unlinked": 0,
                "contact_calls_ambiguous": 0,
                "contact_calls_processed": 0,
            }

        try:
            leads = await _maybe_await(self.amocrm.get_leads_detailed(limit=limit))
        except Exception as exc:
            logger.error("[CALL] Failed to fetch leads: %s", exc)
            return {"leads_scanned": 0, "calls_processed": 0}

        scanned = 0
        processed = 0
        for lead in leads or []:
            if self._defer_calls_without_fallback():
                logger.info(
                    "[CALL] Gemini quota cooldown active; deferring remaining lead recordings."
                )
                break
            lead_id = lead.get("id")
            if not lead_id:
                continue
            scanned += 1
            phone = self._extract_lead_phone(lead)
            phone_getter = getattr(self.amocrm, "get_primary_contact_phone", None)
            if not phone and callable(phone_getter):
                phone = await _maybe_await(phone_getter(lead))
            try:
                processed += await self.process_call_recordings_for_lead(
                    int(lead_id),
                    caller_phone=phone,
                    responsible_user_id=lead.get("responsible_user_id"),
                    write=write,
                    include_transcript=include_transcript,
                    one_analysis_per_lead=one_analysis_per_lead,
                    max_calls_per_lead=max_calls_per_lead,
                    min_call_duration_seconds=min_call_duration_seconds,
                )
            except Exception as exc:
                logger.error("[CALL] Lead processing failed: lead_id=%s error=%s", lead_id, exc)

        contact_stats = await self.analyze_recent_contact_calls(
            limit=min(max(int(limit), 1), 250),
            write=write,
            include_transcript=include_transcript,
            min_call_duration_seconds=min_call_duration_seconds,
        )
        processed += contact_stats["contact_calls_processed"]
        return {
            "leads_scanned": scanned,
            "calls_processed": processed,
            **contact_stats,
        }
