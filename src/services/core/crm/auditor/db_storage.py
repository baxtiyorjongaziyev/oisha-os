"""
Database storage and recent lead fetching mixin for CRM Contacts Auditor.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    cleaned = re.sub(r"[^\d+]", "", phone)
    if not cleaned.startswith("+") and cleaned.startswith("998"):
        cleaned = "+" + cleaned
    elif not cleaned.startswith("+") and len(cleaned) == 9:
        cleaned = "+998" + cleaned
    return cleaned if len(cleaned) >= 9 else None


async def _maybe_await(val: Any) -> Any:
    if hasattr(val, "__await__"):
        return await val
    return val


class DatabaseStorageMixin:
    """Handles SQLite persistence for audit results and recent lead fetching."""

    async def init_db(self) -> None:
        """Create crm_contacts_audit table in the database."""
        if not self.db:
            logger.warning("[AUDITOR] No DB instance, skipping table creation.")
            return
        
        try:
            conn = await self.db.get_connection()
            await _maybe_await(
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS crm_contacts_audit (
                        lead_id INTEGER PRIMARY KEY,
                        lead_name TEXT,
                        contact_id INTEGER,
                        contact_name TEXT,
                        phone TEXT,
                        username TEXT,
                        telegram_user_id INTEGER,
                        call_summary TEXT,
                        telegram_history TEXT,
                        category TEXT,
                        explanation TEXT,
                        audited_at TEXT
                    )
                    """
                )
            )
            await _maybe_await(conn.commit())
            
            # Add new columns if they don't exist
            try:
                await _maybe_await(conn.execute("ALTER TABLE crm_contacts_audit ADD COLUMN detailed_summary TEXT"))
            except Exception:
                logger.debug("[CRM_AUDIT] detailed_summary column may already exist", exc_info=True)
            try:
                await _maybe_await(conn.execute("ALTER TABLE crm_contacts_audit ADD COLUMN task_text TEXT"))
            except Exception:
                logger.debug("[CRM_AUDIT] task_text column may already exist", exc_info=True)
            await _maybe_await(conn.commit())
            
            logger.info("[AUDITOR] crm_contacts_audit table initialized successfully.")
        except Exception as e:
            logger.error("[AUDITOR] Database initialization failed: %s", e)

    async def is_lead_audited(self, lead_id: int) -> bool:
        """Check if a lead has already been audited."""
        if not self.db:
            return False
        try:
            conn = await self.db.get_connection()
            cursor = await _maybe_await(
                conn.execute(
                    "SELECT 1 FROM crm_contacts_audit WHERE lead_id = ? LIMIT 1",
                    (lead_id,)
                )
            )
            row = await _maybe_await(cursor.fetchone())
            return row is not None
        except Exception as e:
            logger.error("[AUDITOR] Failed to check audited state for lead %s: %s", lead_id, e)
            return False

    async def save_audit_result(
        self,
        lead_id: int,
        lead_name: str,
        contact_id: Optional[int],
        contact_name: str,
        phone: str,
        username: str,
        telegram_user_id: Optional[int],
        call_summary: str,
        telegram_history: str,
        category: str,
        explanation: str,
        detailed_summary: Optional[str] = None,
        task_text: Optional[str] = None,
    ) -> None:
        """Persist audit result to database."""
        if not self.db:
            return
        try:
            conn = await self.db.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            await _maybe_await(
                conn.execute(
                    """
                    INSERT OR REPLACE INTO crm_contacts_audit
                        (lead_id, lead_name, contact_id, contact_name, phone, username,
                         telegram_user_id, call_summary, telegram_history, category,
                         explanation, detailed_summary, task_text, audited_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead_id,
                        lead_name,
                        contact_id,
                        contact_name,
                        phone,
                        username,
                        telegram_user_id,
                        call_summary,
                        telegram_history,
                        category,
                        explanation,
                        detailed_summary,
                        task_text,
                        now,
                    ),
                )
            )
            await _maybe_await(conn.commit())
            logger.info("[AUDITOR] Audit saved: lead_id=%s contact=%s category=%s", lead_id, contact_name, category)
        except Exception as e:
            logger.error("[AUDITOR] Failed to save audit to DB for lead %s: %s", lead_id, e)

    async def fetch_recent_leads(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch leads page-by-page from AmoCRM."""
        leads: List[Dict[str, Any]] = []
        page = 1
        
        logger.info("[AUDITOR] Fetching leads detailed from AmoCRM (limit=%s)...", limit)
        while len(leads) < limit:
            url = f"{self.amocrm.base_url}/api/v4/leads"
            req_limit = min(250, limit - len(leads))
            params = {
                "limit": req_limit,
                "page": page,
                "with": "contacts",
            }
            try:
                # Runs AmoCRM API request with auth handles
                response = await self.amocrm._request_with_auth(
                    requests.get, url, params=params, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    page_leads = data.get("_embedded", {}).get("leads", [])
                    if not page_leads:
                        break
                    leads.extend(page_leads)
                    if len(page_leads) < req_limit:
                        break
                    page += 1
                else:
                    logger.error("[AUDITOR] Failed to fetch leads page %s: status=%s", page, response.status_code)
                    break
            except Exception as e:
                logger.error("[AUDITOR] Exception in fetch_recent_leads on page %s: %s", page, e)
                break
                
        logger.info("[AUDITOR] Total leads fetched: %s", len(leads))
        return leads[:limit]
