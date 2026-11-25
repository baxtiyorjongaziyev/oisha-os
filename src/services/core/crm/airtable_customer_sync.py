"""Airtable Mijozlar va Loyihalar jadvalidan AmoCRM Pokupateli (Customers) ga toʻliq sinxronizatsiya."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.core.airtable.sync import AirtableSync
from src.services.core.crm.amocrm.sync import AmoCRMSync

logger = logging.getLogger(__name__)


def _as_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and value:
        return _as_number(value[0])
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if v is not None and str(v).strip())
    return str(value).strip()


def _is_buying_customer(fields: Dict[str, Any]) -> bool:
    """Faqat bizdan sotib olgan mijozlarni (kamida 1 ta loyiha yoki toʻlov) aniqlaydi."""
    loyihalar = fields.get("Loyihalari") or []
    loyiha_soni = _as_number(fields.get("Loyiha soni"))
    ltv = _as_number(fields.get("LTV (real tushum)"))
    return bool(loyihalar) or loyiha_soni > 0 or ltv > 0


def _build_customer_note(
    fields: Dict[str, Any],
    linked_projects: List[Dict[str, Any]],
) -> str:
    """Pokupatel kartochkasi uchun toʻliq maʼlumotnoma matnini tuzadi."""
    name = _as_text(fields.get("Mijoz ismi")) or "Nomaʼlum"
    phone = _as_text(fields.get("Telefon raqami")) or "—"
    email = _as_text(fields.get("Email")) or "—"
    brands = _as_text(fields.get("Brands")) or "—"
    activity = _as_text(fields.get("Faoliyat turi")) or "—"
    address = _as_text(fields.get("Manzil")) or "—"
    channel = _as_text(fields.get("Marketing kanali")) or "—"
    ltv = _as_number(fields.get("LTV (real tushum)"))
    debt = _as_number(fields.get("Jami qarzdorlik"))
    project_count = int(_as_number(fields.get("Loyiha soni")) or len(linked_projects))

    lines = [
        f"Airtable Mijoz Profili: {name}",
        f"Telefon: {phone} | Email: {email}",
        f"Brend: {brands} | Faoliyat: {activity}",
        f"Manzil: {address}",
        f"Marketing kanali: {channel}",
        f"Loyihalar soni: {project_count} | LTV: {ltv:,.0f} UZS | Qarzdorlik: {debt:,.0f} UZS",
    ]

    if linked_projects:
        lines.append("")
        lines.append("Loyihalar:")
        for idx, proj in enumerate(linked_projects, start=1):
            pf = proj.get("fields", {})
            p_name = _as_text(pf.get("Loyiha nomi")) or proj.get("id", "Loyiha")
            p_service = _as_text(pf.get("Xizmat turi")) or "—"
            p_stage = _as_text(pf.get("Loyiha bosqichi")) or "—"
            p_price = _as_number(pf.get("Jami loyiha narxi (UZS)"))
            p_paid = _as_number(pf.get("Jami toʻlangan (UZS)"))
            p_debt = _as_number(pf.get("Qoldiq to‘lov (UZS)"))
            p_start = _as_text(pf.get("Start sana")) or "—"
            p_end = _as_text(pf.get("END sana")) or "—"
            lines.append(
                f"{idx}. {p_name} [{p_service}] — Bosqich: {p_stage} | "
                f"Narx: {p_price:,.0f} | Toʻlangan: {p_paid:,.0f} | Qoldiq: {p_debt:,.0f} | "
                f"Sana: {p_start} → {p_end}"
            )

    return "\n".join(lines)


class AirtableAmoCRMCustomerSync:
    """Airtable Mijozlar + Loyihalar → AmoCRM Pokupateli sinxronizatori."""

    def __init__(
        self,
        amocrm: Optional[AmoCRMSync] = None,
        mijozlar_airtable: Optional[AirtableSync] = None,
        loyihalar_airtable: Optional[AirtableSync] = None,
    ) -> None:
        self.amocrm = amocrm or AmoCRMSync()
        self.mijozlar_airtable = mijozlar_airtable or AirtableSync(table_name="Mijozlar")
        self.loyihalar_airtable = loyihalar_airtable or AirtableSync(table_name="Loyihalar")

    def _resolve_contact_id(self, name: str, phone: str) -> Optional[int]:
        if not phone:
            return None
        existing = self.amocrm.get_contact_by_phone(phone)
        if existing and existing.get("id"):
            return int(existing["id"])
        created_id = self.amocrm.create_contact(name=name, phone=phone)
        return int(created_id) if created_id else None

    def _collect_tags(self, fields: Dict[str, Any]) -> List[str]:
        tags = ["Airtable"]
        services = fields.get("Xizmat turi")
        if isinstance(services, list):
            tags.extend(str(s).strip() for s in services if str(s).strip())
        elif isinstance(services, str) and services.strip():
            tags.append(services.strip())
        channel = _as_text(fields.get("Marketing kanali"))
        if channel:
            tags.append(channel)
        return list(dict.fromkeys(tags))

    def _sync_project_transactions(
        self, customer_id: int, linked_projects: List[Dict[str, Any]]
    ) -> int:
        """Har bir toʻlangan loyiha uchun pokupatelga tranzaksiya yozadi."""
        added = 0
        for proj in linked_projects:
            pf = proj.get("fields", {})
            paid = int(_as_number(pf.get("Jami toʻlangan (UZS)")))
            if paid <= 0:
                continue
            p_name = _as_text(pf.get("Loyiha nomi")) or proj.get("id", "Loyiha")
            p_service = _as_text(pf.get("Xizmat turi"))
            comment = f"{p_name} ({p_service})" if p_service else p_name
            if self.amocrm.add_customer_transaction(
                customer_id=customer_id,
                price=paid,
                comment=comment,
            ):
                added += 1
        return added

    def sync_all(
        self,
        *,
        force_refresh: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Barcha sotib olgan Airtable mijozlarini AmoCRM pokupateli sifatida shakllantiradi."""
        customers = self.mijozlar_airtable.get_projects(force_refresh=force_refresh)
        projects = self.loyihalar_airtable.get_projects(force_refresh=force_refresh)
        projects_by_id = {p.get("id"): p for p in projects if p.get("id")}

        stats: Dict[str, Any] = {
            "total_airtable_customers": len(customers),
            "buying_customers": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "dry_run": dry_run,
        }

        for record in customers:
            fields = record.get("fields", {})
            if not _is_buying_customer(fields):
                stats["skipped"] += 1
                continue

            stats["buying_customers"] += 1
            raw_name = _as_text(fields.get("Mijoz ismi"))
            if not raw_name:
                stats["skipped"] += 1
                continue

            brands = _as_text(fields.get("Brands"))
            customer_name = f"{raw_name} ({brands})" if brands and brands.lower() not in raw_name.lower() else raw_name
            phone = _as_text(fields.get("Telefon raqami"))
            debt = int(_as_number(fields.get("Jami qarzdorlik")))
            tags = self._collect_tags(fields)

            linked_ids = fields.get("Loyihalari") or []
            linked_projects = [projects_by_id[pid] for pid in linked_ids if pid in projects_by_id]
            note_text = _build_customer_note(fields, linked_projects)

            if dry_run:
                continue

            try:
                contact_id = self._resolve_contact_id(raw_name, phone)
                existing_customer = self.amocrm.find_customer(
                    name=customer_name, contact_id=contact_id
                )

                if existing_customer and existing_customer.get("id"):
                    cid = int(existing_customer["id"])
                    self.amocrm.update_customer(
                        customer_id=cid,
                        name=customer_name,
                        next_price=debt if debt > 0 else 0,
                        tags=tags,
                    )
                    if contact_id:
                        existing_contacts = existing_customer.get("_embedded", {}).get("contacts", [])
                        if not any(c.get("id") == contact_id for c in existing_contacts):
                            self.amocrm.link_contact_to_customer(cid, contact_id)
                    self.amocrm.add_customer_note(cid, note_text)
                    self._sync_project_transactions(cid, linked_projects)
                    stats["updated"] += 1
                else:
                    cid = self.amocrm.create_customer(
                        name=customer_name,
                        contact_id=contact_id,
                        next_price=debt if debt > 0 else 0,
                        tags=tags,
                    )
                    if cid:
                        self.amocrm.add_customer_note(int(cid), note_text)
                        self._sync_project_transactions(int(cid), linked_projects)
                        stats["created"] += 1
                    else:
                        stats["errors"] += 1
            except Exception as exc:
                logger.error(f"[AIRTABLE_CUSTOMER_SYNC] {customer_name} xatosi: {exc}")
                stats["errors"] += 1

        return stats
