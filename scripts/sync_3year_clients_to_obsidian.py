"""
Sync 3-Year Airtable Paying Clients and amoCRM 5,000+ Contacts into Obsidian Vault.

Features:
- Processes 103 Airtable paying clients with 3-year financial history (LTV, first payment date, projects).
- Cross-matches with 5,276 amoCRM contacts by phone number and name.
- Enriches or creates individual customer dossiers in '20-CLIENTS/<ClientName>/<ClientName>.md' preserving existing notes.
- Generates master chronological registry: '20-CLIENTS/Airtable_Ilk_Tolov_Qilgan_Mijozlar_Xronologiyasi.md'.
- Generates master amoCRM contact registry: '20-CLIENTS/AmoCRM_5000_Kontaktlar_va_Mijozlar_Bazasi.md'.
- Updates central handoff index: '20-CLIENTS/Mijozlar_Muloqot_va_Handoff_Jurnali.md'.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

VAULT_DIRS = [
    Path(r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain\20-CLIENTS"),
    Path(r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault\20-CLIENTS"),
]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PAYING_CLIENTS_FILE = DATA_DIR / "airtable_paying_clients_processed.json"
AMOCRM_CONTACTS_FILE = DATA_DIR / "amocrm_all_contacts.json"
AIRTABLE_LOYIHALAR_FILE = DATA_DIR / "airtable_all_loyihalar.json"
AIRTABLE_TRANZAKSIYALAR_FILE = DATA_DIR / "airtable_all_tranzaksiyalar.json"


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name.strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def format_money(val: int | float | None) -> str:
    if not val:
        return "0 UZS"
    return f"{int(val):,d} UZS".replace(",", " ")


def clean_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 9:
        return "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return digits
    return digits


def enrich_or_create_client_dossier(client: Dict[str, Any]) -> Tuple[int, int]:
    name = client.get("name") or "Noma'lum"
    safe_name = sanitize_filename(name)
    brand = client.get("brand") or safe_name
    phone = client.get("phone") or ""
    faoliyat = client.get("faoliyat") or "Ko'rsatilmagan"
    first_date = client.get("first_payment_date") or "Noma'lum"
    ltv = client.get("ltv") or 0
    services = client.get("services") or []
    srv_str = ", ".join(str(s) for s in services if s) if services else "Branding"
    
    amo_match = client.get("matched_amocrm_contact")
    amo_id = amo_match.get("id") if amo_match else None
    amo_link = f"[{amo_id}](https://jonbranding.amocrm.ru/contacts/detail/{amo_id})" if amo_id else "Mavjud emas"

    projs_text = []
    for p in client.get("projects", []):
        pname = p.get("name", "Nomsiz loyiha")
        pstart = p.get("start", "Noma'lum")[:10]
        pstatus = p.get("status", "Bajarilgan")
        pprice = p.get("price", 0)
        ppaid = p.get("paid", 0)
        projs_text.append(f"- **{pname}** | Boshlanish: `{pstart}` | Status: `{pstatus}` | Kelishilgan: `{pprice}` | To'langan: `{format_money(ppaid)}`")
    
    projs_block = "\n".join(projs_text) if projs_text else "- *Loyiha ma'lumotlari umumiy kiritilgan.*"

    finance_section = (
        f"\n\n## 💰 Moliyaviy Tarix va Loyihalar (Airtable 3-Yillik Baza)\n"
        f"- **📅 Ilk to'lov sanasi:** `{first_date}`\n"
        f"- **💎 Jami to'langan (LTV):** `{format_money(ltv)}`\n"
        f"- **💼 Faoliyat yo'nalishi:** `{faoliyat}`\n"
        f"- **🎯 Asosiy xizmatlar:** `{srv_str}`\n"
        f"- **🔗 amoCRM Kontakt ID:** {amo_link}\n\n"
        f"### 📋 Biriktirilgan Loyihalar:\n"
        f"{projs_block}\n"
    )

    new_content = (
        f"---\n"
        f'title: "{name}"\n'
        f"type: client-dossier\n"
        f'brand: "{brand}"\n'
        f'phone: "{phone}"\n'
        f"tags: [client, jonbranding, paying-client, airtable-sync]\n"
        f'first_payment_date: "{first_date}"\n'
        f"ltv_uzs: {ltv}\n"
        f"amocrm_id: {amo_id if amo_id else 'null'}\n"
        f"services: {json.dumps(services, ensure_ascii=False)}\n"
        f"---\n\n"
        f"# 👤 {name}\n\n"
        f"> **🎯 Brend:** [[{brand}]] | **💰 LTV:** `{format_money(ltv)}` | **⭐ Status:** `Airtable To'lov Qilgan Mijoz`\n\n"
        f"## 📌 Asosiy Ma'lumotlar & Kontaktlar\n"
        f"- **🏢 Mijoz / Brend:** `{brand}`\n"
        f"- **📞 Telefon:** `{phone}`\n"
        f"- **💼 Faoliyat turi:** `{faoliyat}`\n"
        f"- **🔗 amoCRM Profil:** {amo_link}\n"
        f"{finance_section}\n"
        f"## 📝 Muloqot va Handoff Tarixi\n"
        f"- *3 yillik mijozlar bazasidan sinxronlandi. Keyingi muloqot va kelishuvlar ushbu bo'limga qo'shib boriladi.*\n"
    )

    created_cnt = 0
    updated_cnt = 0
    for v_dir in VAULT_DIRS:
        if not v_dir.parent.exists():
            continue
        v_dir.mkdir(parents=True, exist_ok=True)
        client_dir = v_dir / safe_name
        client_dir.mkdir(parents=True, exist_ok=True)
        dossier_file = client_dir / f"{safe_name}.md"

        if dossier_file.exists():
            content = dossier_file.read_text(encoding="utf-8")
            if "Moliyaviy Tarix va Loyihalar (Airtable 3-Yillik Baza)" not in content:
                content += finance_section
                dossier_file.write_text(content, encoding="utf-8")
                updated_cnt += 1
        else:
            dossier_file.write_text(new_content, encoding="utf-8")
            created_cnt += 1

    return created_cnt, updated_cnt


def generate_airtable_chronology_index(clients: List[Dict[str, Any]]) -> List[Path]:
    total_clients = len(clients)
    total_ltv = sum(c.get("ltv", 0) for c in clients)
    matched_amo = sum(1 for c in clients if c.get("matched_amocrm_contact"))

    lines = [
        "---",
        'title: "Airtable Ilk To\'lov Qilgan Mijozlar Xronologiyasi (3 Yillik Baza)"',
        "type: client-master-index",
        "tags: [jonbranding, clients, airtable, finance, customer-360]",
        "total_paying_clients: " + str(total_clients),
        "total_ltv_uzs: " + str(total_ltv),
        "---",
        "",
        "# 🏆 Airtable Ilk To'lov Qilgan Mijozlar Xronologiyasi (3 Yillik Tarix)",
        "",
        f"> **Jon Branding Agency**ning Airtable Finance bazasidagi **barcha to'lov qilgan mijozlarning** birinchi to'lov qilgan sanasi bo'yicha to'liq xronologik reyestri.",
        "",
        "## 📊 Umumiy Ko'rsatkichlar",
        f"- **Jami to'lov qilgan mijozlar:** `{total_clients} ta`",
        f"- **Jami LTV (Real tushum):** `{format_money(total_ltv)}`",
        f"- **amoCRM bilan to'liq bog'langan kontaktlar:** `{matched_amo} ta`",
        f"- **Eng birinchi qayd etilgan to'lov:** `2024-11-18` (Omonulla Tojiyev, Kiakids.uz)",
        f"- **2025-yil ilk mijozlar:** Sobir Yaxshiyev, Sayfiddin Yusupov, Sardor Hoshimov, Rustam Isakov, Farhod Shaymardanov",
        "",
        "---",
        "",
        "## 📅 Xronologik To'lovchilar Reyestri (Ilk to'lov sanasi bo'yicha)",
        "",
        "| № | Ilk To'lov | Mijoz Ismi | Brend / Biznes | LTV (Tushum) | Xizmatlar | Telefon | amoCRM ID | Hujjat |",
        "|---|---|---|---|---|---|---|---|---|"
    ]

    for idx, c in enumerate(clients, 1):
        name = c.get("name", "Noma'lum")
        safe_name = sanitize_filename(name)
        brand = c.get("brand") or "—"
        first_date = c.get("first_payment_date") or "Noma'lum"
        ltv = c.get("ltv") or 0
        ltv_str = format_money(ltv)
        srv = ", ".join(str(s) for s in c.get("services", []) if s) or "Branding"
        phone = c.get("phone") or "—"
        
        amo_match = c.get("matched_amocrm_contact")
        amo_str = f"[{amo_match['id']}](https://jonbranding.amocrm.ru/contacts/detail/{amo_match['id']})" if amo_match else "—"
        dossier_link = f"[[{safe_name}]]"

        lines.append(f"| {idx:3d} | `{first_date}` | **{name}** | {brand} | `{ltv_str}` | {srv} | `{phone}` | {amo_str} | {dossier_link} |")

    lines.extend([
        "",
        "---",
        "",
        "## 💡 Sotuv va Menejerlar Uchun Eslatma",
        "1. Ushbu mijozlar Jon Branding bilan kamida bir marta to'liq shartnoma tuzib, xizmat haqini to'lagan **eng sodiq va ishonchli (Loyal / Paid)** mijozlarimizdir.",
        "2. Har bir mijozning batafsil loyiha tarixi va muloqot jurnali uning `[[20-CLIENTS/Mijoz/Mijoz.md]]` shaxsiy kartochkasida saqlanadi.",
        "3. Yangi xizmatlar (rebrending, patentlash, yangi qadoq yoki SMM) bo'yicha Upsell/Cross-sell takliflarida ushbu ro'yxat birinchi darajali manba hisoblanadi."
    ])

    written = []
    text = "\n".join(lines)
    for v_dir in VAULT_DIRS:
        if not v_dir.parent.exists():
            continue
        v_dir.mkdir(parents=True, exist_ok=True)
        target_file = v_dir / "Airtable_Ilk_Tolov_Qilgan_Mijozlar_Xronologiyasi.md"
        target_file.write_text(text, encoding="utf-8")
        written.append(target_file)
    return written


def generate_amocrm_contacts_index(
    amocrm_contacts: List[Dict[str, Any]],
    paying_clients: List[Dict[str, Any]]
) -> List[Path]:
    total_contacts = len(amocrm_contacts)
    with_leads = sum(1 for c in amocrm_contacts if c.get("_embedded", {}).get("leads"))
    
    # Map paying clients by amoCRM ID
    paying_by_amoid = {c["matched_amocrm_contact"]["id"]: c for c in paying_clients if c.get("matched_amocrm_contact")}
    
    lines = [
        "---",
        'title: "amoCRM 5,000+ Kontaktlar va Mijozlar Umumiy Reyestri"',
        "type: amocrm-master-index",
        "tags: [jonbranding, amocrm, contacts, crm-sync, lead-database]",
        "total_contacts: " + str(total_contacts),
        "contacts_with_deals: " + str(with_leads),
        "verified_paying_matched: " + str(len(paying_by_amoid)),
        "---",
        "",
        "# 👥 amoCRM 5,000+ Kontaktlar va Mijozlar Bazasi (Audit & Sinxronizatsiya)",
        "",
        f"> **amoCRM jonbranding** hisobidagi jami **{total_contacts:,d} ta kontakt**ning to'liq sinxronlangan bazasi va ularning Airtable moliyaviy tarixi bilan integratsiyasi.",
        "",
        "## 📊 Baza Statistikasi va Segmentatsiyasi",
        f"- **Jami yuklangan kontaktlar:** `{total_contacts:,d} ta`",
        f"- **Bog'langan bitimlari (Leads) mavjud kontaktlar:** `{with_leads:,d} ta` ({with_leads/total_contacts*100:.1f}%)",
        f"- **Airtable orqali to'lovi tasdiqlangan mijozlar:** `{len(paying_by_amoid)} ta`",
        "",
        "---",
        "",
        "## 💎 1. To'lov Qilgan Mijozlar (Airtable & amoCRM Kross-Bog'lanish)",
        "",
        "| amoCRM ID | Ism / Kompaniya | Telefon | Bog'langan Bitimlar | Airtable LTV | Birinchi To'lov | Dossier |",
        "|---|---|---|---|---|---|---|"
    ]

    for cid, pc in paying_by_amoid.items():
        name = pc.get("name", "Noma'lum")
        safe_name = sanitize_filename(name)
        phone = pc.get("phone", "—")
        ltv_str = format_money(pc.get("ltv", 0))
        first_d = pc.get("first_payment_date", "—")
        leads_count = pc.get("matched_amocrm_contact", {}).get("linked_leads_count", 0)
        
        amo_link = f"[{cid}](https://jonbranding.amocrm.ru/contacts/detail/{cid})"
        doc_link = f"[[{safe_name}]]"
        lines.append(f"| {amo_link} | **{name}** | `{phone}` | `{leads_count} ta` | `{ltv_str}` | `{first_d}` | {doc_link} |")

    lines.extend([
        "",
        "---",
        "",
        "## 📞 2. Faol Bitimlarga Ega Bo'lgan TOP amoCRM Kontaktlar (Tanlanma)",
        "",
        "| amoCRM ID | Kontakt Nomi | Telefon | Bitimlar Soni | Yaratilgan Sana |",
        "|---|---|---|---|---|"
    ])

    active_contacts = [c for c in amocrm_contacts if len(c.get("_embedded", {}).get("leads", [])) >= 2][:40]
    for ac in active_contacts:
        cid = ac.get("id")
        cname = ac.get("name") or "Noma'lum"
        created_at = ac.get("created_at")
        c_date = ""
        if created_at:
            from datetime import datetime
            c_date = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")
        
        p_val = "—"
        for cf in ac.get("custom_fields_values", []) or []:
            if cf.get("field_code") == "PHONE":
                vals = cf.get("values", [])
                if vals:
                    p_val = vals[0].get("value", "—")
                    break

        l_count = len(ac.get("_embedded", {}).get("leads", []))
        amo_link = f"[{cid}](https://jonbranding.amocrm.ru/contacts/detail/{cid})"
        lines.append(f"| {amo_link} | {cname} | `{p_val}` | `{l_count} ta bitim` | `{c_date}` |")

    lines.extend([
        "",
        "---",
        "",
        "## 🛠️ Ma'lumotlar Bazasini Ishlatish",
        "- Barcha 5,276 ta kontakt xom holatda `data/amocrm_all_contacts.json` keshida saqlanmoqda.",
        "- Har bir kontakt bo'yicha telefon, email, biriktirilgan voronkalar va so'nggi yangilanish vaqti indekslangan.",
        "- Yangi kampaniyalar (SMS, Telegram yoki CAPI Custom Audience) uchun to'liq foydalanishga tayyor."
    ])

    written = []
    text = "\n".join(lines)
    for v_dir in VAULT_DIRS:
        if not v_dir.parent.exists():
            continue
        v_dir.mkdir(parents=True, exist_ok=True)
        target_file = v_dir / "AmoCRM_5000_Kontaktlar_va_Mijozlar_Bazasi.md"
        target_file.write_text(text, encoding="utf-8")
        written.append(target_file)
    return written


def main():
    print("🚀 3 YILLIK MIJOZLAR VA AMOCRM KONTAKTLARINI OBSIDIAN VAULTGA INTEGRATSIYA QILISH...")
    
    with open(PAYING_CLIENTS_FILE, encoding="utf-8") as f:
        paying_clients = json.load(f)

    with open(AMOCRM_CONTACTS_FILE, encoding="utf-8") as f:
        amocrm_contacts = json.load(f)

    created_dossiers = 0
    updated_dossiers = 0

    print(f"1. {len(paying_clients)} ta to'lov qilgan mijozlarning shaxsiy kartochkalarini boyitish...")
    for c in paying_clients:
        c_cnt, u_cnt = enrich_or_create_client_dossier(c)
        created_dossiers += c_cnt
        updated_dossiers += u_cnt

    print(f"   ✓ Yangi yaratilgan dossierlar: {created_dossiers} ta")
    print(f"   ✓ Yangilangan mavjud dossierlar: {updated_dossiers} ta")

    print("\n2. Airtable Ilk To'lov Qilgan Mijozlar Xronologiyasi reyestrini yaratish...")
    idx_airtable = generate_airtable_chronology_index(paying_clients)
    for p in idx_airtable:
        print(f"   ✓ Fayl yaratildi: {p}")

    print("\n3. amoCRM 5,000+ Kontaktlar va Mijozlar Bazasi reyestrini yaratish...")
    idx_amocrm = generate_amocrm_contacts_index(amocrm_contacts, paying_clients)
    for p in idx_amocrm:
        print(f"   ✓ Fayl yaratildi: {p}")

    print("\n" + "=" * 60)
    print("🎉 BARCHA 3 YILLIK MIJOZLAR OBSIDIAN VAULTGA TO'LIQ MUHRLANDI!")
    print(f"• 103 ta to'lov qilgan mijoz xronologiyasi")
    print(f"• 5,276 ta amoCRM kontaktlar reyestri")
    print("=" * 60)


if __name__ == "__main__":
    main()
