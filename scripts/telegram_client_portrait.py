"""
Telegram Client Portrait Script

This script looks up a client in the Oisha‑OS Google Sheets database by phone number or Telegram username,
assembles a concise "portrait" of the client, appends it to the Obsidian vault via `brain_append`, and, if the client
has a paid lead in AmoCRM, fills missing fields in the Airtable "Mijozlar" table.

The script follows Oisha‑OS Rule 6 (≤ 400 LOC) and respects the single‑workspace restriction.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ----- Configuration -----------------------------------------------------------
SPREADSHEET_ID = "1oOZUPZOti_CIdUkLUgWSdLOrXwQP5rPLjmBywx3wino"  # Jon Branding CRM sheet
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parents[2] / "data" / "service_account.json"
# Airtable base and table (identified from previous discovery)
AIRTABLE_BASE_ID = "app8xoyx1XCumYFXV"
AIRTABLE_TABLE_ID = "tblYeFpWhQIMmrWPZ"  # Mijozlar

# ----- Logging --------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ----- Helper functions -------------------------------------------------------

def normalize_phone(p: str) -> list[str]:
    """Extract Uzbek phone numbers and return them in E.164 format (+998xxxxxxxx)."""
    digits = re.sub(r"[^0-9]", "", p)
    results = []
    if digits.startswith("998") and len(digits) == 12:
        results.append(f"+{digits}")
    if len(digits) == 9:
        results.append(f"+998{digits}")
    if digits.startswith("0") and len(digits) == 10:
        results.append(f"+998{digits[1:]}")
    return list(set(results))

def extract_telegrams(text: str) -> list[str]:
    """Return lower‑cased Telegram usernames (without leading '@')."""
    if not text:
        return []
    candidates = re.findall(r"@([A-Za-z0-9_]+)", text)
    candidates += re.findall(r"Username[:\s]+([A-Za-z0-9_]+)", text, flags=re.I)
    return [c.lower() for c in set(candidates)]

def clean_contact_name(name: str) -> str:
    """Strip suffixes like "TN6" and punctuation, return a human readable name."""
    if not name:
        return ""
    name = re.sub(r"\bTN\d+\b", "", name, flags=re.I)
    name = re.sub(r"[^\w\s\-]", "", name)
    return " ".join(name.split()).strip()

def load_worksheet(gc, title: str):
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(title)

def find_rows(ws, phone_set: set[str], tg_set: set[str]):
    """Return list of row indices (1‑based) that match phone or telegram."""
    rows = []
    values = ws.get_all_values()
    for idx, row in enumerate(values, start=1):
        phones = set(normalize_phone(row[0] or ""))
        tgs = set(extract_telegrams(row[1] or ""))
        if phones & phone_set or tgs & tg_set:
            rows.append(idx)
    return rows

def assemble_portrait(ws, row_idx: int) -> dict:
    """Extract fields from a CRM row and return a portrait dictionary."""
    row = ws.row_values(row_idx)
    portrait = {
        "Name": clean_contact_name(row[0] or ""),
        "Phones": list(set(normalize_phone(row[1] or ""))),
        "Telegram": list(set(extract_telegrams(row[2] or ""))),
        "Company": row[3] or "-",
        "Title": row[4] or "-",
        "Notes": row[5] or "-",
        "CRM Lead ID": row[6] or "-",
        "Seller": row[7] or "-",
        "Stage": row[8] or "-",
        "DupCount": row[9] or "0",
        "Source": row[10] or "-",
    }
    return portrait

def format_portrait_md(portrait: dict) -> str:
    lines = ["## Client Portrait", ""]
    for key, val in portrait.items():
        if isinstance(val, list):
            val = ", ".join(val) if val else "-"
        lines.append(f"- **{key}**: {val}")
    return "\n".join(lines)

def brain_append_md(content: str):
    """Append markdown to Obsidian via the brain MCP tool."""
    from antigravity.mcp import call_mcp_tool
    args = {"location": "20-CLIENTS", "content": content, "allow_overwrite": False}
    call_mcp_tool({"Arguments": args, "ServerName": "brain", "ToolName": "brain_append", "toolAction": "Appending portrait", "toolSummary": "Obsidian write"})

def airtable_update_missing(record_id: str, missing: dict):
    from antigravity.mcp import call_mcp_tool
    payload = {"base_id": AIRTABLE_BASE_ID, "table_id": AIRTABLE_TABLE_ID, "records": [{"id": record_id, "fields": missing}]}
    call_mcp_tool({"Arguments": payload, "ServerName": "airtable", "ToolName": "update_records", "toolAction": "Updating Airtable", "toolSummary": "Airtable sync"})

def find_airtable_record_by_phone(phone: str) -> str | None:
    from antigravity.mcp import call_mcp_tool
    formula = f"{{Phone}} = '{phone}'"
    args = {"base_id": AIRTABLE_BASE_ID, "table_id": AIRTABLE_TABLE_ID, "formula": formula, "max_records": 1}
    resp = call_mcp_tool({"Arguments": args, "ServerName": "airtable", "ToolName": "search_records", "toolAction": "Searching Airtable", "toolSummary": "Airtable lookup"})
    try:
        return resp["records"][0]["id"]
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate a client portrait from Telegram input.")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--phone", help="Phone number in any format (e.g. +998901234567)")
    grp.add_argument("--username", help="Telegram username (without @)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Obsidian or Airtable")
    args = parser.parse_args()

    # Lock handling
    agents_md = Path(__file__).resolve().parents[2] / "AGENTS.md"
    lock_line = "- telegram_client_portrait (running)"
    try:
        with agents_md.open("a", encoding="utf-8") as f:
            f.write(f"\n{lock_line}\n")
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        crm_ws = load_worksheet(gc, "CRM")
        phone_set = set(normalize_phone(args.phone)) if args.phone else set()
        tg_set = {args.username.lower()} if args.username else set()
        rows = find_rows(crm_ws, phone_set, tg_set)
        if not rows:
            logging.info("No matching client found in CRM sheet.")
            return
        portrait = assemble_portrait(crm_ws, rows[0])
        md = format_portrait_md(portrait)
        logging.info("Portrait assembled for %s", portrait.get("Name"))
        if not args.dry_run:
            brain_append_md(md)
            if portrait.get("Stage", "").lower() in {"sotuv", "sold", "paid"}:
                for p in portrait["Phones"]:
                    rec_id = find_airtable_record_by_phone(p)
                    if rec_id:
                        missing = {}
                        for field in ["Company", "Title", "Notes"]:
                            if portrait.get(field) and portrait[field] != "-":
                                missing[field] = portrait[field]
                        if missing:
                            airtable_update_missing(rec_id, missing)
                        break
        else:
            logging.info("Dry run – not writing to Obsidian or Airtable.")
    finally:
        try:
            lines = agents_md.read_text(encoding="utf-8").splitlines()
            with agents_md.open("w", encoding="utf-8") as f:
                for l in lines:
                    if l.strip() != lock_line.strip():
                        f.write(l + "\n")
        except Exception as e:
            logging.warning("Failed to clean lock line: %s", e)

if __name__ == "__main__":
    main()
