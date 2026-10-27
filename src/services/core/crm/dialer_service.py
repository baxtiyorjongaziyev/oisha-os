"""Jon CRM — 9-Pipeline Kanban, Focus Dialer, BANT/SPIN Deal Card, and Twenty CRM Invisible Backend Engine.

Architecture:
- Frontend UI (`/sotuv`) looks and works 1:1 like amoCRM (9 pipelines, Kanban Drag-and-Drop, 21 BANT/SPIN fields, tags, files, AI coaching).
- Invisible Backend Engine is Twenty CRM (`crm.jonbranding.uz`) paired with local SQLite (`DialerStore`) read-through/write-through cache for sub-10ms responsiveness.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import requests

from src.services.core.crm.dialer_store import DialerStore
from src.services.core.crm.pipelines_catalog import (
    AMO_CF_ID_TO_KEY,
    CRM_SELLERS,
    DEAL_CUSTOM_FIELDS_SCHEMA,
    PIPELINES_CATALOG,
    SELLER_ID_TO_NAME,
    get_pipeline_by_id,
    resolve_status_info,
)
from src.services.core.crm.twenty_client import TwentyClient

logger = logging.getLogger(__name__)

AMOCRM_TO_SLUG: Dict[int, str] = {
    st["id"]: st["slug"]
    for p in PIPELINES_CATALOG
    for st in p["statuses"]
}
AMOCRM_TO_SLUG[87609514] = "yangi"

SLUG_TO_AMOCRM: Dict[str, int] = {
    st["slug"]: st["id"]
    for p in PIPELINES_CATALOG
    for st in p["statuses"]
}
SLUG_TO_AMOCRM["kotarmadi"] = 87609518

SLUG_TO_TWENTY: Dict[str, str] = {
    st["slug"]: st["twenty"]
    for p in PIPELINES_CATALOG
    for st in p["statuses"]
}
SLUG_TO_TWENTY["kotarmadi"] = "SCREENING"


class DialerService:
    """Manages Jon CRM (amoCRM 1:1 UI powered by Twenty CRM backend engine)."""

    def __init__(self, store: Optional[DialerStore] = None, twenty: Optional[TwentyClient] = None) -> None:
        self.store = store or DialerStore()
        self.twenty = twenty or TwentyClient()

    def get_catalog(self) -> Dict[str, Any]:
        """Return full catalog of 9 pipelines, 21 custom fields, sellers, and Twenty backend status."""
        stats = self.store.get_stats()
        by_pipe = stats.get("by_pipeline", {})
        pipelines = [
            {**p, "leads_count": by_pipe.get(p["id"], 0)}
            for p in PIPELINES_CATALOG
        ]
        return {
            "backend_engine": "twenty-crm",
            "twenty_base_url": self.twenty.base_url,
            "pipelines": pipelines,
            "custom_fields_schema": DEAL_CUSTOM_FIELDS_SCHEMA,
            "sellers": CRM_SELLERS,
        }

    def get_queue(
        self, rep_id: Optional[int] = None, status: Optional[str] = None, search: Optional[str] = None,
        limit: int = 50, pipeline_id: Optional[int] = None, tag: Optional[str] = None, slim: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch list of queued leads."""
        return self.store.get_queue(
            rep_id=rep_id, status_slug=status, search=search, limit=limit, pipeline_id=pipeline_id, tag=tag, slim=slim,
        )

    def get_next_lead(
        self, rep_id: Optional[int] = None, status: Optional[str] = None,
        exclude_id: Optional[int] = None, pipeline_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the single top-priority lead for the rep."""
        leads = self.store.get_queue(rep_id=rep_id, status_slug=status, limit=15, pipeline_id=pipeline_id)
        for lead in leads:
            if exclude_id and lead["id"] == exclude_id:
                continue
            return lead
        return leads[0] if leads else None

    async def save_lead_with_twenty(self, lead_data: Dict[str, Any]) -> int:
        """Create or update a lead in local store and immediately write-through to Twenty CRM backend."""
        pipe_id = int(lead_data.get("pipeline_id") or 11162698)
        st_info = resolve_status_info(pipe_id, status_id=lead_data.get("status_id"), status_slug=lead_data.get("status_slug"))
        lead_data["pipeline_id"] = pipe_id
        lead_data["status_id"] = st_info["id"]
        lead_data.setdefault("status_slug", st_info["slug"])

        lead_id = self.store.create_or_update_lead(lead_data)
        full_lead = self.store.get_lead_detail(lead_id) or lead_data
        twenty_stage = SLUG_TO_TWENTY.get(full_lead.get("status_slug") or "yangi", "NEW")

        asyncio.create_task(self.twenty.upsert_opportunity_full(full_lead, twenty_stage=twenty_stage))
        from src.services.core.crm.amocrm_dialer_syncer import sync_lead_save_to_amocrm
        asyncio.create_task(sync_lead_save_to_amocrm(full_lead))
        return lead_id

    async def submit_action(
        self, lead_id: int, action_slug: str, seller_name: str,
        note: Optional[str] = None, next_call_at: Optional[str] = None, pipeline_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process a call outcome or Kanban Drag-and-Drop stage move and sync to Twenty CRM."""
        existing = self.store.get_lead(lead_id)
        target_pipe = pipeline_id or (existing["pipeline_id"] if existing else 11162698)
        st_info = resolve_status_info(target_pipe, status_slug=action_slug)
        amo_status_id = st_info["id"]
        canonical_slug = "kotarmadi" if action_slug == "kotarmadi" else st_info["slug"]

        self.store.record_call_action(
            lead_id=lead_id, new_status_slug=canonical_slug, new_status_id=amo_status_id,
            seller_name=seller_name, note=note, next_call_at=next_call_at, pipeline_id=target_pipe,
        )
        asyncio.create_task(
            self._sync_external_crms(lead_id, canonical_slug, seller_name, note, target_pipe, amo_status_id)
        )
        return {
            "success": True, "lead_id": lead_id, "pipeline_id": target_pipe,
            "new_status": canonical_slug, "new_status_id": amo_status_id,
            "next_lead": self.get_next_lead(exclude_id=lead_id, pipeline_id=target_pipe),
            "stats": self.store.get_stats(pipeline_id=target_pipe),
        }

    async def _sync_external_crms(
        self, lead_id: int, action_slug: str, seller_name: str, note: Optional[str],
        pipeline_id: int = 11162698, amo_status_id: Optional[int] = None,
    ) -> None:
        """Propagate status change, custom fields, and notes to Twenty CRM backend (and amoCRM)."""
        twenty_stage = SLUG_TO_TWENTY.get(action_slug, "SCREENING")
        try:
            full_lead = self.store.get_lead(lead_id)
            if full_lead:
                opp = await self.twenty.upsert_opportunity_full(full_lead, twenty_stage=twenty_stage)
            else:
                opp = await self.twenty.find_opportunity_by_amo_id(lead_id)
                if opp and "id" in opp:
                    extra = {
                        "pipelineId": pipeline_id,
                        "amoStatusId": amo_status_id or SLUG_TO_AMOCRM.get(action_slug, 87609518),
                        "statusSlug": action_slug,
                    }
                    await self.twenty.update_opportunity_stage(opp["id"], twenty_stage, extra_fields=extra)
            if note and opp and "id" in opp:
                await self.twenty.add_timeline_note(
                    title=f"Bosqich: {action_slug.upper()}", body=f"{seller_name}: {note}", target_opportunity_id=opp["id"],
                )
        except Exception as exc:
            logger.warning("[dialer-sync] Twenty sync error for lead %s: %s", lead_id, exc)

        try:
            from src.services.core.crm.amocrm_dialer_syncer import sync_action_to_amocrm
            status_val = amo_status_id or resolve_status_info(pipeline_id, status_slug=action_slug)["id"]
            await sync_action_to_amocrm(
                lead_id=lead_id, status_id=status_val, pipeline_id=pipeline_id, note=note, seller_name=seller_name
            )
        except Exception as exc:
            logger.warning("[dialer-sync] amoCRM sync error for lead %s: %s", lead_id, exc)

        try:
            from src.services.core.crm.digital_pipeline import DigitalPipelineEngine
            await DigitalPipelineEngine().execute_stage_enter_triggers(
                lead_id=lead_id, pipeline_id=pipeline_id, new_stage_slug=action_slug, seller_name=seller_name,
            )
        except Exception as dp_exc:
            logger.debug("[dialer-sync] DP trigger error: %s", dp_exc)

    async def pull_from_amocrm(self, limit: int = 150, pipeline_id: Optional[int] = None) -> int:
        """Pull leads from amoCRM into Jon CRM store."""
        from src.services.core.crm.amocrm_dialer_syncer import pull_leads_from_amocrm
        return await pull_leads_from_amocrm(limit=limit, pipeline_id=pipeline_id)

    async def pull_from_twenty_backend(self, pipeline_id: Optional[int] = None, limit: int = 600) -> int:
        """Pull Opportunities from Twenty CRM backend (`crm.jonbranding.uz`) into local store."""
        opps = await self.twenty.list_opportunities(pipeline_id=pipeline_id, limit=limit)
        pulled = 0
        for opp in opps:
            lead_dict = self.twenty.opportunity_to_lead_dict(opp)
            if not lead_dict["id"]:
                continue
            self.store.upsert_lead(lead_dict)
            pulled += 1
        return pulled

    async def push_all_to_twenty_backend(self, limit: int = 600, chunk_size: int = 40) -> Dict[str, int]:
        """Push all local Jon CRM leads into Twenty CRM backend (`crm.jonbranding.uz`) using /rest/batch/opportunities."""
        existing_opps = await self.twenty.list_opportunities(limit=1000)
        amo_to_twenty_id: Dict[int, str] = {}
        for opp in existing_opps:
            if opp.get("amoId") and opp.get("id"):
                amo_to_twenty_id[int(opp["amoId"])] = opp["id"]

        leads = self.store.get_queue(limit=limit, include_closed=True)
        to_create: List[Dict[str, Any]] = []
        already_synced = 0
        for lead in leads:
            amo_id = int(lead["id"])
            if amo_id in amo_to_twenty_id:
                already_synced += 1
                continue
            twenty_stage = SLUG_TO_TWENTY.get(lead.get("status_slug") or "yangi", "NEW")
            to_create.append(self.twenty.build_opportunity_payload(lead, twenty_stage=twenty_stage))

        created, failed = 0, 0
        async with httpx.AsyncClient(timeout=45.0) as client:
            for idx in range(0, len(to_create), chunk_size):
                batch = to_create[idx : idx + chunk_size]
                try:
                    res = await client.post(
                        f"{self.twenty.base_url}/rest/batch/opportunities",
                        headers=self.twenty._headers(),
                        json=batch,
                    )
                    if res.status_code in (200, 201):
                        created += len(batch)
                    else:
                        for item in batch:
                            r_one = await client.post(
                                f"{self.twenty.base_url}/rest/opportunities",
                                headers=self.twenty._headers(),
                                json=item,
                            )
                            if r_one.status_code in (200, 201):
                                created += 1
                            else:
                                failed += 1
                            await asyncio.sleep(0.15)
                except Exception:
                    failed += len(batch)
                await asyncio.sleep(0.8)

        return {"total": len(leads), "created": created, "already_synced": already_synced, "failed": failed}

    def get_kanban_board(
        self,
        rep_id: Optional[int] = None,
        pipeline_id: int = 11162698,
        search: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Produce full Kanban board columns for any of the 9 pipelines."""
        pipeline_cfg = get_pipeline_by_id(pipeline_id)
        leads = self.store.get_queue(
            rep_id=rep_id, pipeline_id=pipeline_id, search=search, tag=tag, limit=1000, include_closed=True, slim=True
        )
        statuses = pipeline_cfg["statuses"]
        columns: Dict[str, List[Dict[str, Any]]] = {st["slug"]: [] for st in statuses}
        default_slug = statuses[1]["slug"] if len(statuses) > 1 else statuses[0]["slug"]

        for lead in leads:
            slug = lead.get("status_slug") or default_slug
            if slug == "kotarmadi" and "kotarmadi" not in columns:
                slug = "qayta_aloqa" if "qayta_aloqa" in columns else default_slug
            if slug not in columns:
                slug = resolve_status_info(pipeline_id, status_id=lead.get("status_id"), status_slug=slug)["slug"]
            columns.setdefault(slug, []).append(lead)

        total_sum = sum(float(l.get("price") or 0.0) for l in leads)
        return {
            "backend_engine": "twenty-crm",
            "pipeline_id": pipeline_cfg["id"],
            "pipeline_name": pipeline_cfg["name"],
            "stages": [
                {
                    "id": st["id"],
                    "slug": st["slug"],
                    "title": st["title"],
                    "color": st["color"],
                    "twenty": st.get("twenty", "NEW"),
                    "count": len(columns.get(st["slug"], [])),
                    "sum": sum(float(l.get("price") or 0.0) for l in columns.get(st["slug"], [])),
                    "leads": columns.get(st["slug"], []),
                }
                for st in statuses
            ],
            "total_leads": len(leads),
            "total_sum": total_sum,
        }

    def generate_ai_deal_analysis(self, lead_id: int) -> Dict[str, Any]:
        """Generate structured BANT/SPIN AI coaching and call analysis for a deal."""
        lead = self.store.get_lead_detail(lead_id)
        if not lead:
            return {"error": "Lead not found"}

        cf = lead.get("custom_fields") or {}
        notes = lead.get("notes") or []
        price = float(lead.get("price") or 0.0)
        stage_slug = lead.get("status_slug") or "yangi"
        brand = cf.get("brand_name") or lead.get("company_name") or lead.get("name") or "Mijoz brendi"
        service = cf.get("service_type") or "Brending & Patentlash"
        if isinstance(service, list):
            service = ", ".join(service)
        pain = cf.get("pain_point") or cf.get("ai_need_summary") or "Bozorda ajralib turish, nomni patentlash va ishonchni oshirish"
        decision = cf.get("decision_role") or "Asoschi (Founder)"
        budget_fit = cf.get("budget_fit") or (f"{int(price):,} so'm".replace(",", " ") if price > 0 else "Aniqlashtirilmoqda")

        bant_score = 45 + (15 if lead.get("phone") else 0) + (15 if (price > 0 or cf.get("budget_fit")) else 0)
        if cf.get("pain_point") or cf.get("service_type"):
            bant_score += 15
        if stage_slug in ("uchrashuv", "uchrashuvga_keldi", "jarayonda", "sotuv"):
            bant_score += 10
        bant_score = min(100, bant_score)

        analysis = {
            "bant_score": bant_score,
            "sentiment": "Yuqori qiziqish (Issiq)" if bant_score >= 75 else "O'rta (Iliq — saralash kerak)",
            "summary": f"{brand} ({lead.get('contact_name') or 'Mijoz'}) — {service} bo'yicha murojaat. Qaror qiluvchi: {decision}. Byudjet holati: {budget_fit}. Jami izohlar/aloqalar: {len(notes)} ta.",
            "pain_point": pain,
            "recommendations": [
                f"1. SPIN (Muammo): '{brand}' loyihasida mijozning asosiy og'rig'i ({pain}) bo'yicha 2 ta raqobatchi keysi va patent himoyasi xavfini ko'rsating.",
                f"2. Qiymat & KP: {service} bo'yicha 3 bosqichli tijoriy taklif (Start / Optimal / Kompleks Brendbuk) taqdim eting.",
                "3. Keyingi qadam (Closing): Telefonda narx aytib qoldirmasdan, Baxtiyorjon Gaziyev yoki katta strateg bilan 20 daqiqalik diagnostika uchrashuvini belgilang.",
            ],
            "next_best_action": cf.get("next_step") or "Zoom/Ofis uchrashuv vaqtini tasdiqlash va brifni to'ldirish",
            "analyzed_at": "Hozir (Oisha AI + Twenty CRM)",
        }
        self.store.save_ai_analysis(lead_id, analysis)
        return analysis

    def seed_from_backup_file(
        self, backup_path: str = "backups/amocrm_pre_pcg_toshkent7_backup_20261024.json", include_lost: bool = False
    ) -> int:
        """Import leads, contacts, companies, tags, and custom fields from amoCRM backup snapshot."""
        path = Path(backup_path)
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        contacts_by_id: Dict[int, Dict[str, Any]] = {}
        for c in data.get("contacts", []):
            phone, email = "", ""
            for cf in c.get("custom_fields_values") or []:
                vals = cf.get("values") or []
                if vals and cf.get("field_code") == "PHONE" and not phone:
                    phone = str(vals[0].get("value") or "").strip()
                elif vals and cf.get("field_code") == "EMAIL" and not email:
                    email = str(vals[0].get("value") or "").strip()
            contacts_by_id[c["id"]] = {"name": c.get("name") or "", "phone": phone, "email": email}

        companies_by_id = {comp["id"]: comp.get("name") or "" for comp in data.get("companies", [])}
        ingested = 0
        for item in data.get("leads", []):
            status_id = item.get("status_id") or 0
            if status_id == 143 and not include_lost:
                continue
            pipe_id = item.get("pipeline_id") or 11162698
            st_info = resolve_status_info(pipe_id, status_id=status_id)
            emb = item.get("_embedded") or {}
            c_list = emb.get("contacts") or []
            c_info = contacts_by_id.get(c_list[0]["id"], {}) if c_list and "id" in c_list[0] else {}
            comp_list = emb.get("companies") or []
            comp_name = companies_by_id.get(comp_list[0]["id"], "") if comp_list and "id" in comp_list[0] else ""
            tags = [t.get("name") for t in (emb.get("tags") or []) if t.get("name")]
            cf_dict: Dict[str, Any] = {}
            for cf in item.get("custom_fields_values") or []:
                key = AMO_CF_ID_TO_KEY.get(cf.get("field_id")) or cf.get("field_name")
                vals = cf.get("values") or []
                if key and vals:
                    cf_dict[key] = [v.get("value") for v in vals] if len(vals) > 1 else vals[0].get("value")
            rep_id = item.get("responsible_user_id")
            self.store.upsert_lead({
                "id": item["id"],
                "pipeline_id": pipe_id,
                "name": item.get("name") or f"Bitim #{item['id']}",
                "contact_name": c_info.get("name") or "",
                "company_name": comp_name or cf_dict.get("brand_name") or "",
                "phone": c_info.get("phone") or "",
                "email": c_info.get("email") or "",
                "price": float(item.get("price") or 0.0),
                "status_id": status_id,
                "status_slug": st_info["slug"],
                "responsible_user_id": rep_id,
                "responsible_name": SELLER_ID_TO_NAME.get(rep_id, "Shahnoza Abdijabborova"),
                "source": str(cf_dict.get("lead_source") or (tags[0] if tags else "amoCRM")),
                "tags": tags,
                "custom_fields": cf_dict,
                "is_active": status_id != 143,
            })
            ingested += 1
        return ingested
