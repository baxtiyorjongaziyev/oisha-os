"""Twenty CRM Client — REST & GraphQL adapter for Self-Hosted Twenty CRM (`crm.jonbranding.uz`).

Provides asynchronous integration with Twenty CRM instances as the primary invisible backend for:
- People (Contacts)
- Companies
- Opportunities (Deals / 9 Pipelines / BANT & SPIN Custom Fields)
- Notes & Call Timelines
- Tasks & Reminders
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class TwentyAuthError(RuntimeError):
    """Twenty CRM autentifikatsiya xatosi (API key mavjud emas yoki yaroqsiz)."""
    pass


DEFAULT_AMO_STAGE_MAP = {
    87609510: "NEW",
    89067962: "NEW",
    87609518: "SCREENING",
    87609522: "SCREENING",
    87609526: "MEETING",
    89380154: "MEETING",
    88871066: "PROPOSAL",
    142: "CUSTOMER",
    143: "PROPOSAL",
}


class TwentyClient:
    """Async HTTP Client for Twenty CRM REST and GraphQL APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        from src.settings import settings

        self.base_url = (
            base_url
            or getattr(settings, "TWENTY_BASE_URL", None)
            or os.getenv("TWENTY_BASE_URL")
            or "https://crm.jonbranding.uz"
        ).rstrip("/")
        if api_key is not None:
            self.api_key = api_key or None
        else:
            self.api_key = (
                getattr(settings, "TWENTY_API_KEY", None)
                or os.getenv("TWENTY_API_KEY")
                or None
            )
        self.timeout = timeout

    def _headers(self, require_auth: bool = True) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif require_auth:
            raise TwentyAuthError(
                "TWENTY_API_KEY sozlanmagan. Iltimos, .env yoki settings'da TWENTY_API_KEY ni belgilang."
            )
        return headers

    async def health_check(self) -> bool:
        """Verify Twenty CRM connectivity via /healthz."""
        url = f"{self.base_url}/healthz"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._headers(require_auth=False))
                return res.status_code == 200
        except Exception as exc:
            logger.warning("[twenty-crm] health check failed: %s", exc)
            return False

    async def find_person_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Search for a Person (contact) by phone number."""
        clean_phone = phone.replace(" ", "").replace("-", "").strip()
        url = f"{self.base_url}/rest/people"
        params = {"filter[phones][like]": f"%{clean_phone[-9:]}%"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._headers(), params=params)
                if res.status_code == 200:
                    people = res.json().get("data", {}).get("people", [])
                    return people[0] if people else None
        except Exception as exc:
            logger.error("[twenty-crm] find_person_by_phone error: %s", exc)
        return None

    async def find_person_by_amo_id(self, amo_id: int) -> Optional[Dict[str, Any]]:
        """Search for a Person (contact) by amoCRM ID."""
        url = f"{self.base_url}/rest/people"
        params = {"filter[amoId][eq]": str(amo_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._headers(), params=params)
                if res.status_code == 200:
                    people = res.json().get("data", {}).get("people", [])
                    return people[0] if people else None
        except Exception as exc:
            logger.error("[twenty-crm] find_person_by_amo_id error: %s", exc)
        return None

    async def find_opportunity_by_amo_id(self, amo_id: int) -> Optional[Dict[str, Any]]:
        """Search for an Opportunity (deal) by amoCRM ID."""
        url = f"{self.base_url}/rest/opportunities"
        params = {"filter[amoId][eq]": str(amo_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._headers(), params=params)
                if res.status_code == 200:
                    opps = res.json().get("data", {}).get("opportunities", [])
                    return opps[0] if opps else None
        except Exception as exc:
            logger.error("[twenty-crm] find_opportunity_by_amo_id error: %s", exc)
        return None

    async def list_opportunities(
        self,
        pipeline_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Fetch Opportunities from Twenty CRM with cursor pagination."""
        url = f"{self.base_url}/rest/opportunities"
        results: List[Dict[str, Any]] = []
        after_cursor: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                while len(results) < limit:
                    batch_size = min(60, limit - len(results))
                    params: Dict[str, Any] = {"limit": batch_size}
                    if pipeline_id is not None:
                        params["filter[pipelineId][eq]"] = str(pipeline_id)
                    if after_cursor:
                        params["starting_after"] = after_cursor
                    res = await client.get(url, headers=self._headers(), params=params)
                    if res.status_code != 200:
                        break
                    body = res.json()
                    opps = body.get("data", {}).get("opportunities", [])
                    if not opps:
                        break
                    results.extend(opps)
                    page_info = body.get("pageInfo") or {}
                    if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
                        break
                    after_cursor = page_info["endCursor"]
        except Exception as exc:
            logger.error("[twenty-crm] list_opportunities error: %s", exc)
        return results

    @staticmethod
    def build_opportunity_payload(lead_data: Dict[str, Any], twenty_stage: str = "NEW") -> Dict[str, Any]:
        """Convert Jon CRM / amoCRM lead dict into Twenty CRM Opportunity REST payload."""
        amount = float(lead_data.get("price") or 0.0)
        cf = lead_data.get("custom_fields") or {}
        tags = lead_data.get("tags") or []
        files = lead_data.get("files") or []
        ai = lead_data.get("ai_analysis") or {}
        payload: Dict[str, Any] = {
            "name": (lead_data.get("name") or f"Bitim #{lead_data.get('id', '')}")[:250],
            "stage": twenty_stage,
            "amount": {"amountMicros": int(amount * 1_000_000), "currencyCode": "UZS"},
            "amoId": int(lead_data["id"]) if lead_data.get("id") else None,
            "pipelineId": int(lead_data.get("pipeline_id") or 11162698),
            "amoStatusId": int(lead_data.get("status_id") or 0),
            "statusSlug": str(lead_data.get("status_slug") or "yangi"),
            "responsibleUserId": int(lead_data["responsible_user_id"]) if lead_data.get("responsible_user_id") else None,
            "responsibleName": str(lead_data.get("responsible_name") or ""),
            "contactName": str(lead_data.get("contact_name") or ""),
            "companyName": str(lead_data.get("company_name") or cf.get("brand_name") or ""),
            "contactPhone": str(lead_data.get("phone") or ""),
            "painPoint": str(cf.get("pain_point") or cf.get("ai_need_summary") or ""),
            "nextStep": str(cf.get("next_step") or ""),
            "tagsJson": json.dumps(tags, ensure_ascii=False),
            "customFieldsJson": json.dumps(cf, ensure_ascii=False),
            "filesJson": json.dumps(files, ensure_ascii=False),
            "aiAnalysisJson": json.dumps(ai, ensure_ascii=False),
            "lastAudioUrl": str(lead_data.get("last_audio_url") or ""),
            "lastAudioDuration": int(lead_data.get("last_audio_duration") or 0),
            "callsCount": int(lead_data.get("calls_count") or 0),
        }
        return {k: v for k, v in payload.items() if v is not None}

    @staticmethod
    def opportunity_to_lead_dict(opp: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Twenty CRM Opportunity object into Jon CRM / amoCRM 1:1 lead format."""
        amt_obj = opp.get("amount") or {}
        micros = float(amt_obj.get("amountMicros") or 0.0)
        price = micros / 1_000_000.0

        def _parse_json(raw: Any, default: Any) -> Any:
            if not raw or not isinstance(raw, str):
                return default
            try:
                return json.loads(raw)
            except Exception:
                return default

        return {
            "id": int(opp.get("amoId") or 0),
            "twenty_id": opp.get("id"),
            "pipeline_id": int(opp.get("pipelineId") or 11162698),
            "name": opp.get("name") or "Nomsiz Bitim",
            "contact_name": opp.get("contactName") or "",
            "company_name": opp.get("companyName") or "",
            "phone": opp.get("contactPhone") or "",
            "price": price,
            "status_id": int(opp.get("amoStatusId") or 0),
            "status_slug": opp.get("statusSlug") or "yangi",
            "responsible_user_id": opp.get("responsibleUserId"),
            "responsible_name": opp.get("responsibleName") or "Shahnoza Abdijabborova",
            "tags": _parse_json(opp.get("tagsJson"), []),
            "custom_fields": _parse_json(opp.get("customFieldsJson"), {}),
            "files": _parse_json(opp.get("filesJson"), []),
            "ai_analysis": _parse_json(opp.get("aiAnalysisJson"), {}),
            "last_audio_url": opp.get("lastAudioUrl") or None,
            "last_audio_duration": int(opp.get("lastAudioDuration") or 0),
            "calls_count": int(opp.get("callsCount") or 0),
            "updated_at": opp.get("updatedAt"),
        }

    async def upsert_opportunity_full(self, lead_data: Dict[str, Any], twenty_stage: str = "NEW") -> Optional[Dict[str, Any]]:
        """Create or update an Opportunity in Twenty CRM with all Jon CRM / amoCRM fields."""
        amo_id = int(lead_data["id"]) if lead_data.get("id") else None
        payload = self.build_opportunity_payload(lead_data, twenty_stage=twenty_stage)
        existing = await self.find_opportunity_by_amo_id(amo_id) if amo_id else None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if existing and existing.get("id"):
                    url = f"{self.base_url}/rest/opportunities/{existing['id']}"
                    res = await client.patch(url, headers=self._headers(), json=payload)
                    if res.status_code in (200, 204):
                        return res.json().get("data", {}).get("updateOpportunity") or existing
                else:
                    url = f"{self.base_url}/rest/opportunities"
                    res = await client.post(url, headers=self._headers(), json=payload)
                    if res.status_code in (200, 201):
                        return res.json().get("data", {}).get("createOpportunity")
                logger.error("[twenty-crm] upsert_opportunity_full failed: %s %s", res.status_code, res.text[:200])
        except Exception as exc:
            logger.error("[twenty-crm] upsert_opportunity_full exception: %s", exc)
        return None

    async def create_person(
        self, first_name: str, last_name: str = "", phone: Optional[str] = None,
        email: Optional[str] = None, job_title: Optional[str] = None, amo_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new contact (Person) in Twenty CRM."""
        url = f"{self.base_url}/rest/people"
        payload: Dict[str, Any] = {"name": {"firstName": first_name or "Mijoz", "lastName": last_name or ""}}
        if phone:
            payload["phones"] = {"primaryPhoneNumber": phone}
        if email:
            payload["emails"] = {"primaryEmail": email}
        if job_title:
            payload["jobTitle"] = job_title
        if amo_id:
            payload["amoId"] = amo_id
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code in (200, 201):
                    return res.json().get("data", {}).get("createPerson")
                logger.error("[twenty-crm] create_person failed: %s %s", res.status_code, res.text)
        except Exception as exc:
            logger.error("[twenty-crm] create_person exception: %s", exc)
        return None

    async def create_opportunity(
        self, name: str, stage: str = "NEW", amount: float = 0.0, person_id: Optional[str] = None,
        company_id: Optional[str] = None, owner_id: Optional[str] = None,
        amo_id: Optional[int] = None, close_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new Deal/Opportunity in Twenty CRM."""
        url = f"{self.base_url}/rest/opportunities"
        payload: Dict[str, Any] = {
            "name": name, "stage": stage,
            "amount": {"amountMicros": int(amount * 1_000_000), "currencyCode": "UZS"},
        }
        for key, val in [("pointOfContactId", person_id), ("companyId", company_id), ("ownerId", owner_id), ("amoId", amo_id), ("closeDate", close_date)]:
            if val is not None:
                payload[key] = val
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code in (200, 201):
                    return res.json().get("data", {}).get("createOpportunity")
                logger.error("[twenty-crm] create_opportunity failed: %s %s", res.status_code, res.text)
        except Exception as exc:
            logger.error("[twenty-crm] create_opportunity exception: %s", exc)
        return None

    async def update_opportunity_stage(
        self, opportunity_id: str, stage: str, extra_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update the pipeline stage and optional custom fields of an existing Opportunity."""
        url = f"{self.base_url}/rest/opportunities/{opportunity_id}"
        payload: Dict[str, Any] = {"stage": stage, **(extra_fields or {})}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.patch(url, headers=self._headers(), json=payload)
                return res.status_code in (200, 204)
        except Exception as exc:
            logger.error("[twenty-crm] update_opportunity_stage exception: %s", exc)
            return False

    async def add_timeline_note(
        self, body: str, title: str = "Qo'ng'iroq qaydi",
        target_person_id: Optional[str] = None, target_opportunity_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Attach an activity/note to a Person or Opportunity timeline."""
        url = f"{self.base_url}/rest/notes"
        payload: Dict[str, Any] = {"title": title, "bodyV2": {"markdown": body}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code in (200, 201):
                    note = res.json().get("data", {}).get("createNote")
                    note_id = note.get("id") if note else None
                    if note_id and (target_person_id or target_opportunity_id):
                        t_payload = {k: v for k, v in [("noteId", note_id), ("targetPersonId", target_person_id), ("targetOpportunityId", target_opportunity_id)] if v}
                        await client.post(f"{self.base_url}/rest/noteTargets", headers=self._headers(), json=t_payload)
                    return note
                logger.error("[twenty-crm] add_timeline_note failed: %s", res.text)
        except Exception as exc:
            logger.error("[twenty-crm] add_timeline_note exception: %s", exc)
        return None

    async def create_task(
        self, title: str, body: str = "", due_at: Optional[str] = None, assignee_id: Optional[str] = None,
        target_person_id: Optional[str] = None, target_opportunity_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a scheduled task or reminder in Twenty CRM."""
        url = f"{self.base_url}/rest/tasks"
        payload: Dict[str, Any] = {"title": title, "bodyV2": {"markdown": body}, "status": "TODO"}
        if due_at:
            payload["dueAt"] = due_at
        if assignee_id:
            payload["assigneeId"] = assignee_id
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code in (200, 201):
                    task = res.json().get("data", {}).get("createTask")
                    task_id = task.get("id") if task else None
                    if task_id and (target_person_id or target_opportunity_id):
                        t_payload = {k: v for k, v in [("taskId", task_id), ("targetPersonId", target_person_id), ("targetOpportunityId", target_opportunity_id)] if v}
                        await client.post(f"{self.base_url}/rest/taskTargets", headers=self._headers(), json=t_payload)
                    return task
                logger.error("[twenty-crm] create_task failed: %s", res.text)
        except Exception as exc:
            logger.error("[twenty-crm] create_task exception: %s", exc)
        return None

    async def get_workspace_members(self) -> List[Dict[str, Any]]:
        """Fetch all workspace members / sellers from Twenty CRM."""
        url = f"{self.base_url}/rest/workspaceMembers"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    return res.json().get("data", {}).get("workspaceMembers", [])
        except Exception as exc:
            logger.error("[twenty-crm] get_workspace_members error: %s", exc)
        return []
