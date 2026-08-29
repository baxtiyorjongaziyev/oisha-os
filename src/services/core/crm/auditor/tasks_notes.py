"""
CRM lead task extraction, deduplication, and call note analysis mixin.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TasksNotesMixin:
    """Handles CRM tasks, notes, and call transcript serialization."""

    def serialize_lead_details(self, lead: Dict[str, Any]) -> str:
        """Serialize AmoCRM lead/deal parameters to pass to Gemini."""
        details = []
        details.append(f"Bitim ID: {lead.get('id')}")
        details.append(f"Bitim Nomi: {lead.get('name')}")
        details.append(f"Narxi: {lead.get('price')} UZS")

        created_at = lead.get("created_at")
        if created_at:
            try:
                date_str = datetime.fromtimestamp(int(created_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                details.append(f"Yaratilgan sana: {date_str}")
            except Exception:
                logger.debug("[CRM_AUDIT] Failed to format created_at timestamp", exc_info=True)

        closed_at = lead.get("closed_at")
        if closed_at:
            try:
                date_str = datetime.fromtimestamp(int(closed_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                details.append(f"Yopilgan sana: {date_str}")
            except Exception:
                logger.debug("[CRM_AUDIT] Failed to format closed_at timestamp", exc_info=True)

        details.append(f"Mas'ul xodim ID (Responsible User): {lead.get('responsible_user_id')}")
        details.append(f"Status (Pipeline Stage) ID: {lead.get('status_id')}")
        details.append(f"Voronka (Pipeline) ID: {lead.get('pipeline_id')}")
        
        loss_reason = lead.get("loss_reason_id")
        if loss_reason:
            details.append(f"Muvaffaqiyatsizlik sababi ID (Loss Reason): {loss_reason}")

        # Tags
        tags = lead.get("_embedded", {}).get("tags", []) or lead.get("tags", [])
        tag_names = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
        if tag_names:
            details.append(f"Teglar: {', '.join(tag_names)}")

        # Custom Fields
        cfs = lead.get("custom_fields_values") or []
        cf_details = []
        for cf in cfs:
            name = cf.get("field_name") or cf.get("field_code") or "Noma'lum maydon"
            vals = [str(v.get("value")) for v in cf.get("values") or [] if v.get("value") is not None]
            if vals:
                cf_details.append(f"- {name}: {', '.join(vals)}")
        if cf_details:
            details.append("Qo'shimcha maydonlar:\n" + "\n".join(cf_details))

        return "\n".join(details)

    async def get_lead_tasks(self, lead_id: int) -> List[Dict[str, Any]]:
        """Fetch tasks (both active and completed) for a specific lead."""
        tasks = []
        for is_completed in [0, 1]:
            url = f"{self.amocrm.base_url}/api/v4/tasks"
            params = {
                "filter[entity_id]": lead_id,
                "filter[entity_type]": "leads",
                "filter[is_completed]": is_completed
            }
            try:
                response = await self.amocrm._request_with_auth(
                    requests.get, url, params=params, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    page_tasks = data.get("_embedded", {}).get("tasks", [])
                    tasks.extend(page_tasks)
            except Exception as e:
                logger.error("[AUDITOR] Failed to fetch tasks for lead %s (is_completed=%s): %s", lead_id, is_completed, e)
        return tasks

    def serialize_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Convert lead tasks history and comments into structured string."""
        if not tasks:
            return "Bitimda vazifalar tarixi mavjud emas."
        lines = []
        for t in tasks:
            status = "Bajarilgan" if t.get("is_completed") else "Faol"
            created = ""
            if t.get("created_at"):
                try:
                    created = datetime.fromtimestamp(int(t.get("created_at")), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    logger.debug("[CRM_AUDIT] Failed to format task created_at timestamp", exc_info=True)
            text = t.get("text") or "Tavsifsiz vazifa"
            result_info = ""
            if t.get("is_completed") and t.get("result"):
                res_text = t.get("result", {}).get("text") or "Izohsiz"
                result_info = f" | Bajarilish izohi (javobi): {res_text}"
            
            lines.append(f"- [{status}] Yaratilgan: {created} | Vazifa: {text}{result_info}")
        return "\n".join(lines)

    def is_duplicate_task(self, new_task_text: str, existing_tasks: List[Dict[str, Any]]) -> bool:
        """Check if new_task_text is similar to any existing active or completed task."""
        if not new_task_text:
            return False
            
        def clean_text(t: str) -> str:
            # Lowercase, keep letters/numbers, strip
            t_clean = re.sub(r"[^\w\s]", "", t.lower())
            t_clean = t_clean.replace("oisha-os keyingi qadam", "").strip()
            t_clean = t_clean.replace("oishaos", "").strip()
            return t_clean
            
        new_cleaned = clean_text(new_task_text)
        if not new_cleaned:
            return False
            
        new_words = set(new_cleaned.split())
        if not new_words:
            return False
            
        for t in existing_tasks:
            ext_text = t.get("text") or ""
            ext_cleaned = clean_text(ext_text)
            if not ext_cleaned:
                continue
                
            # Exact match check
            if new_cleaned == ext_cleaned or new_cleaned in ext_cleaned or ext_cleaned in new_cleaned:
                return True
                
            # Word overlap check (e.g. if 70% of words overlap)
            ext_words = set(ext_cleaned.split())
            if not ext_words:
                continue
            intersection = new_words.intersection(ext_words)
            smaller_len = min(len(new_words), len(ext_words))
            if smaller_len > 0 and len(intersection) / smaller_len > 0.7:
                return True
                
        return False

    async def get_call_notes_and_transcripts(
        self, lead_id: int, phone: str
    ) -> Tuple[str, str]:
        """Get processed transcripts/summaries from db or AmoCRM lead notes."""
        transcript = ""
        summary = ""

        # 1. Search locally/Turso DB for processed calls
        if self.db:
            try:
                conn = await self.db.get_connection()
                cursor = await _maybe_await(
                    conn.execute(
                        """
                        SELECT transcript, summary FROM call_analyses 
                        WHERE lead_id = ? OR (caller_phone = ? AND caller_phone != '')
                        ORDER BY analyzed_at DESC LIMIT 1
                        """,
                        (lead_id, phone),
                    )
                )
                row = await _maybe_await(cursor.fetchone())
                if row:
                    transcript, summary = row
                    if transcript or summary:
                        logger.info("[AUDITOR] Found existing call analysis in DB for lead %s.", lead_id)
                        return transcript, summary
            except Exception as e:
                logger.debug("[AUDITOR] DB call lookup failed: %s", e)

        # 2. Look for existing Oisha call notes in AmoCRM
        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
            for note in notes or []:
                text = str((note.get("params") or {}).get("text") or "")
                # If this is Oisha call tahlili note, grab the text
                if "Oisha-OS: Qo'ng'iroq tahlili" in text or "Qo'ng'iroq tahlili" in text:
                    summary = text
                    logger.info("[AUDITOR] Found existing call note in AmoCRM for lead %s.", lead_id)
                    break
                    
            # 3. Fallback to basic call notes summary if no transcripts found
            if not summary:
                call_lines = []
                for note in notes or []:
                    note_type = str(note.get("note_type") or "").lower()
                    if note_type in ("call_in", "call_out", "phone_call"):
                        params = note.get("params") or {}
                        duration = params.get("duration", 0)
                        direction = "Kiruvchi" if note_type == "call_in" else "Chiquvchi"
                        created_at = note.get("created_at")
                        date_str = ""
                        if created_at:
                            try:
                                date_str = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                logger.debug("[CRM_AUDIT] Failed to format call note created_at timestamp", exc_info=True)
                        call_lines.append(f"Qo'ng'iroq ({date_str}): {direction}, davomiyligi={duration}s")
                
                if call_lines:
                    summary = "Mavjud qo'ng'iroqlar tarixi:\n" + "\n".join(call_lines)
        except Exception as e:
            logger.error("[AUDITOR] Failed to get call notes from AmoCRM for lead %s: %s", lead_id, e)

        return transcript, summary

    async def get_lead_notes_history(self, lead_id: int) -> str:
        """Fetch and serialize recent text comments/notes for the lead to help classification."""
        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
            if not notes:
                return "Izohlar tarixi bo'sh."
            
            lines = []
            for note in notes[:15]:  # Limit to last 15 notes
                note_type = str(note.get("note_type") or "").lower()
                text = str((note.get("params") or {}).get("text") or "").strip()
                if not text:
                    continue
                
                # Skip Oisha's own long audit and duplicate warnings to avoid context pollution
                if "Oisha-OS: Bitim va Suhbatlar Mukammal Tahlili" in text or "Oisha-OS: Qo'ng'iroq tahlili" in text or "Oisha-OS Eslatma:" in text or "Oisha-OS Telegram Draft:" in text:
                    continue
                
                created_at = note.get("created_at")
                date_str = ""
                if created_at:
                    try:
                        date_str = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        logger.debug("[CRM_AUDIT] Failed to format note created_at timestamp", exc_info=True)
                
                lines.append(f"[{date_str}] ({note_type}): {text}")
            
            if not lines:
                return "Izohlar tarixi bo'sh."
            return "\n".join(lines)
        except Exception as e:
            logger.error("[AUDITOR] Failed to get notes history for lead %s: %s", lead_id, e)
            return "Izohlar tarixi olinmadi (xatolik)."
