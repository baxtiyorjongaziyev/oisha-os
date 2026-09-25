#!/usr/bin/env python3
"""Synchronize Tez Natija 6 database into Jon_Branding_Sotuv_CRM Google Sheet.

Strictly adheres to Oisha-OS Modular Code Standard (Rule 6, <= 400 LOC).
Zero-breaking: Preserves all existing CRM seller notes, statuses, and formulas.
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import unicodedata
from collections import Counter
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TN6Sync")

SPREADSHEET_ID = "1oOZUPZOti_CIdUkLUgWSdLOrXwQP5rPLjmBywx3wino"
SERVICE_ACCOUNT_FILE = "data/service_account.json"
C7_FILE = r"C:\Users\baxti\Downloads\contacts (7).csv"
C6_FILE = r"C:\Users\baxti\Downloads\contacts (6).csv"


def normalize_phone(p: str) -> list[str]:
    """Extract and normalize all valid 998 phone numbers from text."""
    if not p:
        return []
    matches = re.findall(r"(?:\+?998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}|\b\d{9}\b)", p)
    res, seen = [], set()
    for m in matches:
        clean = re.sub(r"\D", "", m)
        if len(clean) == 9:
            clean = "998" + clean
        if len(clean) == 12 and clean.startswith("998"):
            norm = "+" + clean
            if norm not in seen:
                seen.add(norm)
                res.append(norm)
    return res


def extract_telegrams(text: str) -> list[str]:
    """Extract unique telegram @usernames from text."""
    if not text:
        return []
    found = re.findall(r"@[a-zA-Z0-9_]{4,}", text)
    m_uname = re.findall(r"(?:Username|username|TG Username):\s*@?([a-zA-Z0-9_]{4,})", text)
    found.extend([f"@{u}" for u in m_uname])
    res, seen = [], set()
    for u in found:
        low = u.lower()
        if low not in seen:
            seen.add(low)
            res.append(u)
    return res


def clean_contact_name(orig: str) -> str:
    """Normalize and clean contact name, stripping TN suffixes and symbol noise."""
    if not orig:
        return ""
    norm = unicodedata.normalize("NFKD", orig)
    pat = re.compile(
        r"(?:\s*TN\d*\s*(?:Gr|gr)?|\s*TN\s*(?:Gr|gr)?|\s*Tez\s*Natija\s*\d*|\s*TN\d*)+\s*$",
        re.IGNORECASE,
    )
    s = pat.sub("", norm).strip()
    s = re.sub(r"^[\s.,;:_()\-+*!?\"'`~#@^%&=/\\|<>\[\]{}]+", "", s)
    s = re.sub(r"[\s.,;:_()\-+*!?\"'`~#@^%&=/\\|<>\[\]{}]+$", "", s)
    s = s.strip()
    return s if re.search(r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ0-9]", s) else ""


def load_tn6_raw_contacts() -> list[dict]:
    """Load and merge TN6 contacts from contacts (7).csv and contacts (6).csv."""
    with open(C7_FILE, "r", encoding="utf-8") as f:
        tn6_rows = list(csv.DictReader(f))
        for r in tn6_rows:
            r["_source_file"] = "contacts (7).csv"

    with open(C6_FILE, "r", encoding="utf-8") as f:
        c6_rows = list(csv.DictReader(f))

    def k_tup(r: dict) -> tuple:
        return (r.get("First Name", "").strip(), r.get("Last Name", "").strip())

    seen_keys = {k_tup(r) for r in tn6_rows}
    extra_tn6 = []
    for r in c6_rows:
        fn, ln = r.get("First Name", ""), r.get("Last Name", "")
        if ("TN6" in fn or "TN6" in ln) and k_tup(r) not in seen_keys:
            r["_source_file"] = "contacts (6).csv"
            extra_tn6.append(r)
            seen_keys.add(k_tup(r))

    all_raw = tn6_rows + extra_tn6
    logger.info("Loaded %d TN6 contacts (%d from c7, %d extra from c6)", len(all_raw), len(tn6_rows), len(extra_tn6))
    return all_raw


def prepare_raw_rows(all_raw: list[dict], start_id: int) -> list[list[str]]:
    """Format contacts into 'Raw kontaktlar' rows."""
    raw_sheet_rows = []
    for idx, r in enumerate(all_raw):
        rec_id = str(start_id + idx)
        src_file = r.get("_source_file", "contacts (7).csv")
        src_line = str(idx + 2)
        group = "Tez Natija 6"
        orig_name = f"{r.get('First Name', '').strip()} {r.get('Last Name', '').strip()}".strip()
        cleaned_name = clean_contact_name(orig_name)
        phones = normalize_phone(f"{r.get('Phone 1 - Value', '')} {r.get('Phone 2 - Value', '')}")
        tgs = extract_telegrams(f"{r.get('Notes', '')} {orig_name} {r.get('Website 1 - Value', '')}")
        email = r.get("E-mail 1 - Value", "").strip()
        company = r.get("Organization Name", "").strip()
        title = r.get("Organization Title", "").strip()
        notes = r.get("Notes", "").strip()

        raw_sheet_rows.append([
            rec_id, src_file, src_line, group, orig_name, cleaned_name,
            ", ".join(phones), ", ".join(tgs), email, company, title, notes
        ])
    return raw_sheet_rows


def build_pipeline_updates(
    all_raw: list[dict],
    crm_rows: list[list[str]],
    al_rows: list[list[str]],
    raw_rows: list[list[str]],
) -> dict[str, Any]:
    """Calculate mutations for CRM, Aloqasiz, Dublikatlar and Dashboard."""
    crm_by_phone: dict[str, int] = {}
    crm_by_tg: dict[str, int] = {}
    for r_idx, r in enumerate(crm_rows[1:], start=2):
        for p in normalize_phone(r[2]) + normalize_phone(r[3]):
            crm_by_phone[p] = r_idx
        for tg in extract_telegrams(r[4]):
            crm_by_tg[tg.lower()] = r_idx

    raw_by_p: dict[str, str] = {}
    raw_by_t: dict[str, str] = {}
    for r in raw_rows[1:]:
        src = f"{r[1]}:{r[2]}"
        for p in r[6].split(", ") if r[6] else []:
            raw_by_p[p] = src
        for t in r[7].split(", ") if r[7] else []:
            raw_by_t[t.lower()] = src

    sellers_cnt = Counter(r[8] for r in crm_rows[1:] if len(r) > 8 and r[8] in ("Bobur", "Nozima", "Ziyoda"))
    seller_order = sorted(["Bobur", "Nozima", "Ziyoda"], key=lambda s: sellers_cnt[s])

    crm_updates: dict[int, dict] = {}
    crm_appends: list[list[str]] = []
    al_appends: list[list[str]] = []
    dublikat_updates: dict[str, dict] = {}
    processed_phones: dict[str, int] = {}
    processed_tgs: dict[str, int] = {}

    last_crm_num = len(crm_rows) - 1
    last_nc_num = len(al_rows) - 1

    for idx, r in enumerate(all_raw):
        orig_name = f"{r.get('First Name', '').strip()} {r.get('Last Name', '').strip()}".strip()
        cl_name = clean_contact_name(orig_name)
        phones = normalize_phone(f"{r.get('Phone 1 - Value', '')} {r.get('Phone 2 - Value', '')}")
        tgs = extract_telegrams(f"{r.get('Notes', '')} {orig_name} {r.get('Website 1 - Value', '')}")
        company = r.get("Organization Name", "").strip()
        notes = r.get("Notes", "").strip()
        src_line = f"{r.get('_source_file', 'contacts.csv')}:{idx + 2}"

        if not phones and not tgs:
            last_nc_num += 1
            al_appends.append([f"NC-{last_nc_num:04d}", cl_name, orig_name, "Tez Natija 6", notes, "1", src_line])
            continue

        matched_crm_row, dup_key = None, None
        for p in phones:
            if p in crm_by_phone:
                matched_crm_row, dup_key = crm_by_phone[p], f"P:{p}"
                break
        if not matched_crm_row:
            for tg in tgs:
                if tg.lower() in crm_by_tg:
                    matched_crm_row, dup_key = crm_by_tg[tg.lower()], f"T:{tg.lower()}"
                    break

        if matched_crm_row:
            row_data = crm_rows[matched_crm_row - 1]
            existing_grp = row_data[6]
            new_grp = f"{existing_grp}; Tez Natija 6" if "Tez Natija 6" not in existing_grp else existing_grp
            cur_dups = int(row_data[20]) if row_data[20].isdigit() else 1
            new_dups = str(cur_dups + 1)
            orig_lead_name = row_data[21]
            new_orig = f"{orig_lead_name} | {orig_name}" if (orig_name and orig_name not in orig_lead_name) else orig_lead_name

            crm_updates[matched_crm_row] = {"group": new_grp, "dups": new_dups, "orig": new_orig}
            if dup_key:
                orig_src = raw_by_p.get(phones[0] if phones else "", "") or raw_by_t.get(tgs[0].lower() if tgs else "", "contacts.csv:1")
                dublikat_updates[dup_key] = {
                    "main_name": row_data[1] or cl_name, "phones": row_data[2] or ", ".join(phones),
                    "tgs": row_data[4] or ", ".join(tgs), "groups": new_grp, "count": new_dups,
                    "orig_str": new_orig, "src_line": src_line, "orig_src": orig_src,
                }
            continue

        internal_match_idx = None
        for p in phones:
            if p in processed_phones:
                internal_match_idx = processed_phones[p]
                break
        if internal_match_idx is None:
            for tg in tgs:
                if tg.lower() in processed_tgs:
                    internal_match_idx = processed_tgs[tg.lower()]
                    break

        if internal_match_idx is not None:
            new_lead = crm_appends[internal_match_idx]
            new_lead[20] = str(int(new_lead[20]) + 1)
            if orig_name and orig_name not in new_lead[21]:
                new_lead[21] = f"{new_lead[21]} | {orig_name}"
            continue

        last_crm_num += 1
        lead_id = f"LD-{last_crm_num:04d}"
        contact_name = cl_name or (tgs[0] if tgs else (phones[0] if phones else ""))
        p1 = phones[0] if phones else ""
        p2 = phones[1] if len(phones) > 1 else ""
        tg_str = ", ".join(tgs)
        channel = "Telefon + Telegram" if (phones and tgs) else ("Telefon" if phones else "Telegram")

        assigned_seller = seller_order[0]
        sellers_cnt[assigned_seller] += 1
        seller_order = sorted(["Bobur", "Nozima", "Ziyoda"], key=lambda s: sellers_cnt[s])

        new_row = [
            lead_id, contact_name, p1, p2, tg_str, company, "Tez Natija 6", channel,
            assigned_seller, "Yangi lead", "Baholanmagan", "O‘rta", "", "", "Reja yo‘q",
            "0", "", "", "", notes, "1", orig_name
        ]
        curr_idx = len(crm_appends)
        crm_appends.append(new_row)
        for p in phones:
            processed_phones[p] = curr_idx
        for tg in tgs:
            processed_tgs[tg.lower()] = curr_idx

    return {
        "crm_updates": crm_updates, "crm_appends": crm_appends,
        "aloqasiz_appends": al_appends, "dublikat_updates": dublikat_updates,
        "new_last_crm_row": len(crm_rows) + len(crm_appends),
    }


def main():
    parser = argparse.ArgumentParser(description="TN6 CRM Sync")
    parser.add_argument("--dry-run", action="store_true", help="Calculate without writing to sheet")
    args = parser.parse_args()

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    raw_ws = sh.worksheet("Raw kontaktlar")
    crm_ws = sh.worksheet("CRM")
    al_ws = sh.worksheet("Aloqasiz kontaktlar")
    dup_ws = sh.worksheet("Dublikatlar")
    dash_ws = sh.worksheet("Dashboard")

    raw_rows = raw_ws.get_all_values()
    crm_rows = crm_ws.get_all_values()
    al_rows = al_ws.get_all_values()
    dup_rows = dup_ws.get_all_values()

    all_raw = load_tn6_raw_contacts()
    raw_sheet_rows = prepare_raw_rows(all_raw, start_id=len(raw_rows))
    updates = build_pipeline_updates(all_raw, crm_rows, al_rows, raw_rows)

    logger.info("=== SYNC SUMMARY ===")
    logger.info("Raw kontaktlar to append: %d (New total: %d)", len(raw_sheet_rows), len(raw_rows) - 1 + len(raw_sheet_rows))
    logger.info("CRM existing to update: %d", len(updates["crm_updates"]))
    logger.info("CRM brand new to append: %d (New total: %d)", len(updates["crm_appends"]), len(crm_rows) - 1 + len(updates["crm_appends"]))
    logger.info("Aloqasiz kontaktlar to append: %d (New total: %d)", len(updates["aloqasiz_appends"]), len(al_rows) - 1 + len(updates["aloqasiz_appends"]))
    logger.info("Dublikatlar to sync: %d", len(updates["dublikat_updates"]))

    if args.dry_run:
        logger.info("[DRY RUN] Exiting without modifying sheet.")
        return

    # 1. Raw kontaktlar
    logger.info("Appending to Raw kontaktlar...")
    raw_ws.append_rows(raw_sheet_rows, value_input_option="USER_ENTERED")

    # 2. Update CRM
    logger.info("Updating %d existing CRM rows...", len(updates["crm_updates"]))
    crm_batch = []
    for r_idx, u in updates["crm_updates"].items():
        crm_batch.append({"range": f"G{r_idx}", "values": [[u["group"]]]})
        crm_batch.append({"range": f"U{r_idx}", "values": [[u["dups"]]]})
        crm_batch.append({"range": f"V{r_idx}", "values": [[u["orig"]]]})
    if crm_batch:
        crm_ws.batch_update(crm_batch)

    # 3. Append CRM
    logger.info("Appending %d brand new leads to CRM...", len(updates["crm_appends"]))
    crm_ws.append_rows(updates["crm_appends"], value_input_option="USER_ENTERED")

    # 4. Append Aloqasiz
    logger.info("Appending %d rows to Aloqasiz kontaktlar...", len(updates["aloqasiz_appends"]))
    al_ws.append_rows(updates["aloqasiz_appends"], value_input_option="USER_ENTERED")

    # 5. Sync Dublikatlar
    logger.info("Syncing Dublikatlar...")
    dup_keys_existing = {r[0]: idx for idx, r in enumerate(dup_rows[1:], start=2)}
    dup_appends, dup_batch = [], []
    for k, v in updates["dublikat_updates"].items():
        if k in dup_keys_existing:
            row_idx = dup_keys_existing[k]
            dup_batch.append({"range": f"E{row_idx}", "values": [[v["groups"]]]})
            dup_batch.append({"range": f"F{row_idx}", "values": [[v["count"]]]})
            dup_batch.append({"range": f"G{row_idx}", "values": [[v["orig_str"]]]})
            existing_lines = dup_rows[row_idx - 1][7]
            dup_batch.append({"range": f"H{row_idx}", "values": [[f"{existing_lines}; {v['src_line']}"]]})
        else:
            combined_src = f"{v['orig_src']}; {v['src_line']}"
            dup_appends.append([k, v["main_name"], v["phones"], v["tgs"], v["groups"], v["count"], v["orig_str"], combined_src])
    if dup_batch:
        dup_ws.batch_update(dup_batch)
    if dup_appends:
        dup_ws.append_rows(dup_appends, value_input_option="USER_ENTERED")

    # 6. Dashboard
    logger.info("Updating Dashboard...")
    new_last = updates["new_last_crm_row"]
    raw_tot = len(raw_rows) - 1 + len(raw_sheet_rows)
    crm_tot = len(crm_rows) - 1 + len(updates["crm_appends"])
    al_tot = len(al_rows) - 1 + len(updates["aloqasiz_appends"])
    dash_updates = [
        {"range": "B4", "values": [[f"=COUNTA(CRM!A2:A{new_last})"]]},
        {"range": "B5", "values": [[f'=COUNTIF(CRM!H2:H{new_last};"Telefon")+COUNTIF(CRM!H2:H{new_last};"Telefon + Telegram")']]},
        {"range": "B6", "values": [[f'=COUNTIF(CRM!H2:H{new_last};"Telegram")']]},
        {"range": "B7", "values": [[f'=COUNTIF(CRM!J2:J{new_last};"Yangi lead")']]},
        {"range": "B8", "values": [[f'=COUNTIF(CRM!O2:O{new_last};"Bugun")']]},
        {"range": "B9", "values": [[f'=COUNTIF(CRM!O2:O{new_last};"Kechikkan")']]},
        {"range": "B10", "values": [[f'=COUNTIF(CRM!J2:J{new_last};"Sotuv")']]},
        {"range": "B12", "values": [[f'=SUMIF(CRM!J2:J{new_last};"Sotuv";CRM!R2:R{new_last})']]},
        {"range": "B16", "values": [[raw_tot]]},
        {"range": "B17", "values": [[crm_tot + al_tot]]},
        {"range": "B18", "values": [[raw_tot - (crm_tot + al_tot)]]},
        {"range": "B19", "values": [[al_tot]]},
        {"range": "D20", "values": [["Tez Natija 6"]]},
        {"range": "E20", "values": [[f'=COUNTIF(CRM!G2:G{new_last};"*Tez Natija 6*")']]},
    ]
    dash_ws.batch_update(dash_updates, value_input_option="USER_ENTERED")
    logger.info("✅ SUCCESS: Tez Natija 6 fully synchronized into Jon_Branding_Sotuv_CRM!")


if __name__ == "__main__":
    main()
