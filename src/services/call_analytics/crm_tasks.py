import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import structlog
from src.services.core.call_analyses_schema import ensure_call_analysis_schema
from src.services.core.sales_playbook import (
    normalise_outcome,
    outcome_converted,
)
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallCrmTasksMixin:
    async def _is_call_processed(self, call_id: str) -> bool:
        """Return True when this AmoCRM call was already analyzed."""
        if not call_id or not self.db:
            return False
        try:
            conn = await self.db.get_connection()
            execute_result = conn.execute(
                "SELECT 1 FROM call_analyses WHERE call_id = ?", (call_id,)
            )
            if hasattr(execute_result, "__aenter__"):
                async with execute_result as cur:
                    return (await _maybe_await(cur.fetchone())) is not None

            cur = await _maybe_await(execute_result)
            return (await _maybe_await(cur.fetchone())) is not None
        except Exception as exc:
            logger.warning("[CALL] DB processed check failed for %s: %s", call_id, exc)
            return False

    async def _resolve_manager_name(self, responsible_user_id: Optional[int]) -> str:
        """AmoCRM mas'ul foydalanuvchi ID'sidan menejer ismi.

        Ism bo'lmasa murabbiylik qatlami qo'ng'iroqni hech kimga bog'lay
        olmaydi — shuning uchun ID bo'lsa ham hech bo'lmasa uni yozamiz.
        """
        if not responsible_user_id:
            return ""
        try:
            name = await _maybe_await(
                self.amocrm.get_user_name(int(responsible_user_id))
            )
        except Exception as exc:
            logger.warning(
                "[CALL] Menejer ismi olinmadi (user_id=%s): %s", responsible_user_id, exc
            )
            return ""
        return str(name or "").strip()

    async def _log_call_analysis(
        self,
        call_id: str,
        lead_id: int,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        transcript: str,
        audio_url: str,
        caller_phone: str = "",
        task_id: str = "",
        analysis: Optional[Dict[str, Any]] = None,
        duration_seconds: int = 0,
        manager_id: Optional[int] = None,
        manager_name: str = "",
    ) -> None:
        """Tahlilni bazaga yozadi — BALLAR bilan birga.

        Ilgari bu yerga faqat matnli ustunlar tushardi; rubrik ballari
        AmoCRM notasida qolib ketardi va `sales_quality_coach` bo'sh
        ma'lumot ustida ishlardi. Endi murabbiylik qatlami o'qiydigan
        barcha ustunlar saqlanadi.
        """
        if not self.db:
            return

        await ensure_call_analysis_schema(self.db)

        analysis = analysis or {}
        rubrik = analysis.get("rubrik_baholar") or {}
        outcome = normalise_outcome(analysis.get("natija"))
        overall_score = int(analysis.get("sifat_bahosi") or 0)

        def _dump(value: Any) -> str:
            try:
                return json.dumps(value or [], ensure_ascii=False)
            except (TypeError, ValueError):
                return "[]"

        try:
            conn = await self.db.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            task_created_at = now if task_id else None
            await _maybe_await(
                conn.execute(
                    """
                    INSERT OR IGNORE INTO call_analyses
                        (call_id, lead_id, category, summary, client_mood,
                         next_steps, transcript, audio_url, caller_phone,
                         task_id, task_created_at, analyzed_at, created_at, source,
                         manager_id, manager_name, duration_seconds, overall_score,
                         scores, strengths, weaknesses, objections, outcome,
                         converted, client_interest_level,
                         breakdown_at, breakdown_reason,
                         longest_pause_seconds, pauses)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?)
                    """,
                    (
                        call_id,
                        lead_id,
                        category,
                        summary,
                        client_mood,
                        next_steps,
                        transcript,
                        audio_url,
                        caller_phone,
                        task_id,
                        task_created_at,
                        now,
                        now,
                        "amocrm",
                        int(manager_id) if manager_id else None,
                        manager_name,
                        max(int(duration_seconds or 0), 0),
                        overall_score,
                        _dump(rubrik) if rubrik else "{}",
                        _dump(analysis.get("kuchli_tomonlar")),
                        _dump(analysis.get("zaif_tomonlar")),
                        _dump(analysis.get("etirozlar")),
                        outcome,
                        1 if outcome_converted(outcome) else 0,
                        int(analysis.get("lead_bahosi") or 0),
                        analysis.get("uzilish_vaqti"),
                        str(analysis.get("uzilish_sababi") or ""),
                        float(analysis.get("eng_uzun_pauza") or 0.0),
                        _dump(analysis.get("pauzalar")),
                    ),
                )
            )
            await _maybe_await(conn.commit())
            logger.info(
                "[CALL] DB log saved: lead_id=%s call_id=%s ball=%s natija=%s menejer=%s",
                lead_id,
                call_id,
                overall_score,
                outcome,
                manager_name or "?",
            )
        except Exception as exc:
            logger.error("[CALL] DB log failed for %s: %s", call_id, exc)

    async def _notify_telegram_call_analysis(
        self,
        *,
        lead_id: int,
        call_id: str,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        duration_seconds: int,
        manager_name: str,
        caller_phone: str,
        analysis: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> None:
        """Sotuv/CRM guruhiga yangi tahlil qilingan qo'ng'iroq hisobotini yuborish."""
        from src.services.core.calls.call_notifier import send_call_analysis_telegram_alert

        subdomain = getattr(self.amocrm, "subdomain", "jonbranding") if self.amocrm else "jonbranding"
        await send_call_analysis_telegram_alert(
            lead_id=lead_id,
            call_id=call_id,
            category=category,
            summary=summary,
            client_mood=client_mood,
            next_steps=next_steps,
            duration_seconds=duration_seconds,
            manager_name=manager_name,
            caller_phone=caller_phone,
            analysis=analysis,
            task_id=task_id,
            subdomain=subdomain,
        )

    def _should_create_task(
        self,
        next_steps: str,
        agreed_datetime: Optional[datetime] = None,
        conversion_advice: Optional[List[str]] = None,
    ) -> bool:
        if not self.create_tasks:
            return False
        if agreed_datetime is not None:
            return True
        if conversion_advice:
            return True
        text = (next_steps or "").strip()
        if not text:
            return False
        return text.lower() not in {
            "n/a",
            "na",
            "yo'q",
            "yoq",
            "mavjud emas",
            "kerak emas",
            "noaniq",
            "-",
        }

    def _build_task_text(
        self,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        agreed_datetime: Optional[datetime] = None,
        conversion_advice: Optional[List[str]] = None,
    ) -> str:
        action = next_steps if next_steps and next_steps.lower() not in {"n/a", "na", "-"} else "Mijoz bilan follow-up"
        lines = [f"🎯 VAZIFA: {action}"]
        if agreed_datetime is not None:
            weekday = _WEEKDAY_UZ[agreed_datetime.weekday()] if 0 <= agreed_datetime.weekday() < len(_WEEKDAY_UZ) else ""
            lines.append(f"⏰ Kelishilgan vaqt: {agreed_datetime.strftime('%d.%m.%Y %H:%M')} ({weekday})")
        if conversion_advice:
            lines.append(f"💡 Konversiya tavsiyasi: {conversion_advice[0]}")
        lines.append(f"📝 Suhbat xulosasi: {summary}")
        lines.append(f"Toifa: {category} | Kayfiyat: {client_mood}")
        return _clip("\n".join(lines), 900)

    async def _create_follow_up_task(
        self,
        lead_id: int,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        responsible_user_id: Optional[int] = None,
        agreed_datetime: Optional[datetime] = None,
        conversion_advice: Optional[List[str]] = None,
    ) -> str:
        if not self._should_create_task(next_steps, agreed_datetime, conversion_advice):
            return ""

        create_task = getattr(self.amocrm, "create_task", None)
        if not callable(create_task):
            logger.warning("[CALL] AmoCRM client has no create_task method")
            return ""

        if agreed_datetime is not None:
            complete_till = int(agreed_datetime.astimezone(timezone.utc).timestamp())
            logger.info(
                "[CALL] Vazifa suhbatda kelishilgan vaqtga qo'yildi: %s",
                agreed_datetime.isoformat(),
            )
        else:
            complete_till = int(
                (datetime.now(timezone.utc) + timedelta(hours=self.task_due_hours)).timestamp()
            )
        task_text = self._build_task_text(
            category=category,
            summary=summary,
            client_mood=client_mood,
            next_steps=next_steps,
            agreed_datetime=agreed_datetime,
            conversion_advice=conversion_advice,
        )

        try:
            result = await _maybe_await(
                create_task(
                    lead_id,
                    task_text,
                    complete_till,
                    responsible_user_id=responsible_user_id,
                )
            )
            if result:
                task_id = _extract_amocrm_task_id(result)
                logger.info(
                    "[CALL] Follow-up task created for lead %s task_id=%s",
                    lead_id,
                    task_id or "unknown",
                )
                return task_id or "created"
            logger.warning("[CALL] Follow-up task was not created for lead %s", lead_id)
            return ""
        except Exception as exc:
            logger.error("[CALL] Failed to create follow-up task for lead %s: %s", lead_id, exc)
            return ""
