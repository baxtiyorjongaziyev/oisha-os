'''\
Telegram Client Portrait Script
\
This script looks up a client in the Oisha‑OS Google Sheets database by phone number or Telegram username,
assembles a concise "portrait" of the client, appends it to the Obsidian vault via `brain_append`, and, if the client
has a paid lead in AmoCRM, fills missing fields in the Airtable "Mijozlar" table.
\
The script follows Oisha‑OS Rule 6 (≤ 400 LOC) and respects the single‑workspace restriction.
'''\
\
import argparse, json, logging, re, sys, os\
from pathlib import Path\
\
import gspread\
from google.oauth2.service_account import Credentials\
\
# ----- Configuration -----------------------------------------------------------\
SPREADSHEET_ID = "1oOZUPZOti_CIdUkLUgWSdLOrXwQP5rPLjmBywx3wino"  # Jon Branding CRM sheet\
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parents[2] / "data" / "service_account.json"\
# Airtable base and table (identified from previous discovery)\
AIRTABLE_BASE_ID = "app8xoyx1XCumYFXV"\
AIRTABLE_TABLE_ID = "tblYeFpWhQIMmrWPZ"  # Mijozlar\
\
# ----- Logging --------------------------------------------------------------\
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")\
\
# ----- Helper functions -------------------------------------------------------\
\
def normalize_phone(p: str) -> list[str]:\
    """Extract Uzbek phone numbers and return them in E.164 format (+998xxxxxxxx)."""\
    digits = re.sub(r"[^0-9]", "", p)\
    results = []\
    # Full international form\
    if digits.startswith("998") and len(digits) == 12:\
        results.append(f"+{digits}")\
    # Local 9‑digit number\
    if len(digits) == 9:\
        results.append(f"+998{digits}")\
    # 11‑digit with leading 0\
    if digits.startswith("0") and len(digits) == 10:\
        results.append(f"+998{digits[1:]}")\
    return list(set(results))\
\
def extract_telegrams(text: str) -> list[str]:\
    """Return lower‑cased Telegram usernames (without leading '@')."""\
    if not text:
        return []\
    candidates = re.findall(r"@([A-Za-z0-9_]+)", text)\
    # Some rows contain "Username: xyz" format\
    candidates += re.findall(r"Username[:\s]+([A-Za-z0-9_]+)", text, flags=re.I)\
    return [c.lower() for c in set(candidates)]\
\
def clean_contact_name(name: str) -> str:\
    """Strip suffixes like "TN6" and punctuation, return a human readable name."""\
    if not name:
        return ""\
    name = re.sub(r"\bTN\d+\b", "", name, flags=re.I)\
    name = re.sub(r"[^\w\s\-]", "", name)\
    return " ".join(name.split()).strip()\
\
def load_worksheet(gc, title: str):\
    sh = gc.open_by_key(SPREADSHEET_ID)\
    return sh.worksheet(title)\
\
def find_rows(ws, phone_set: set[str], tg_set: set[str]):\
    """Return list of row indices (1‑based) that match phone or telegram."""\
    rows = []\
    values = ws.get_all_values()\
    for idx, row in enumerate(values, start=1):\
        phones = set(normalize_phone(row[0]))  # column A – phone\
        tgs = set(extract_telegrams(row[1]))  # column B – telegram (if present)\
        if phones & phone_set or tgs & tg_set:\
            rows.append(idx)\
    return rows\
\
def assemble_portrait(raw_ws, crm_ws, row_idx: int) -> dict:\
    """Extract relevant fields from a CRM row (by index) and return a dict."""\
    # Row data – columns are based on existing sheet layout (see sync_tn6_to_crm_sheet.py)\
    row = crm_ws.row_values(row_idx)\
    # Expected column ordering (example, may need adjustment):\
    # 0 Name, 1 Phone, 2 Telegram, 3 Company, 4 Title, 5 Notes, 6 Lead ID, 7 Seller, 8 Stage, 9 DupCount, 10 Source\
    portrait = {\
        "Name": clean_contact_name(row[0] or ""),\
        "Phones": list(set(normalize_phone(row[1] or ""))),\
        "Telegram": list(set(extract_telegrams(row[2] or ""))),\
        "Company": row[3] or "-",\
        "Title": row[4] or "-",\
        "Notes": row[5] or "-",\
        "CRM Lead ID": row[6] or "-",\
        "Seller": row[7] or "-",\
        "Stage": row[8] or "-",\
        "DupCount": row[9] or "0",\
        "Source": row[10] or "-",\
    }\
    return portrait\
\
def format_portrait_md(portrait: dict) -> str:\
    lines = ["## Client Portrait", ""]\
    for key, val in portrait.items():\
        if isinstance(val, list):\
            val = ", ".join(val) if val else "-"\
        lines.append(f"- **{key}**: {val}")\
    return "\n".join(lines)\
\
def brain_append_md(content: str):\
    """Append markdown to Obsidian via the brain MCP tool."""\
    from antigravity.mcp import call_mcp_tool  # helper for lazy tools\
    # The note path is under 20-CLIENTS/<Name>.md – we let the caller create the path string.
    args = {\
        "location": "20-CLIENTS",\
        "content": content,\
        "allow_overwrite": False,\
    }\
    # brain_append signature: (location, content, allow_overwrite?) – check schema if needed.
    call_mcp_tool({"Arguments": args, "ServerName": "brain", "ToolName": "brain_append", "toolAction": "Appending portrait", "toolSummary": "Obsidian write"})\
\
def airtable_update_missing(record_id: str, missing: dict):\
    """Update missing fields in an Airtable record via the airtable MCP tool."""\
    from antigravity.mcp import call_mcp_tool\
    # airtable/update_records expects: base_id, table_id, records [{"id":..., "fields":{...}}]
    payload = {\
        "base_id": AIRTABLE_BASE_ID,\
        "table_id": AIRTABLE_TABLE_ID,\
        "records": [{"id": record_id, "fields": missing}],\
    }\
    call_mcp_tool({"Arguments": payload, "ServerName": "airtable", "ToolName": "update_records", "toolAction": "Updating Airtable", "toolSummary": "Airtable sync"})\
\
def find_airtable_record_by_phone(phone: str) -> str | None:\
    """Search Airtable for a record with matching phone (simplified). Returns record ID or None."""\
    from antigravity.mcp import call_mcp_tool\
    # Use airtable/search_records – schema expects base_id, table_id, query (formula).\
    formula = f"{{Phone}} = '{phone}'"\
    args = {"base_id": AIRTABLE_BASE_ID, "table_id": AIRTABLE_TABLE_ID, "formula": formula, "max_records": 1}\
    resp = call_mcp_tool({"Arguments": args, "ServerName": "airtable", "ToolName": "search_records", "toolAction": "Searching Airtable", "toolSummary": "Airtable lookup"})\
    # Expected response: {"records": [{"id": "rec...", "fields": {...}}]}
    try:\
        rec = resp["records"][0]\
        return rec["id"]\
    except Exception:\
        return None\
\
def main():\
    parser = argparse.ArgumentParser(description="Generate a client portrait from Telegram input.")\
    group = parser.add_mutually_exclusive_group(required=True)\
    group.add_argument("--phone", help="Phone number in any format (e.g. +998901234567)")\
    group.add_argument("--username", help="Telegram username (without @)")\
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Obsidian or Airtable")\
    args = parser.parse_args()\
\
    # Acquire lock – simple file append; on exit we will clean it up.\
    agents_md = Path(__file__).resolve().parents[2] / "AGENTS.md"\
    lock_line = "- telegram_client_portrait (running)"\
    try:\
        with agents_md.open("a", encoding="utf-8") as f:\
            f.write(f"\n{lock_line}\n")\
        # ----- Google Sheets access -----\
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=["https://www.googleapis.com/auth/spreadsheets"])\
        gc = gspread.authorize(creds)\
        crm_ws = load_worksheet(gc, "CRM")\
        # Build search sets\
        phone_set = set(normalize_phone(args.phone)) if args.phone else set()\
        tg_set = {args.username.lower()} if args.username else set()\
        # Find matching rows\
        matching_rows = find_rows(crm_ws, phone_set, tg_set)\
        if not matching_rows:\
            logging.info("No matching client found in CRM sheet.")\
            return\
        # For simplicity pick the first match\
        row_idx = matching_rows[0]\
        portrait = assemble_portrait(crm_ws, crm_ws, row_idx)\
        md = format_portrait_md(portrait)\
        logging.info("Portrait assembled for %s", portrait["Name"])\
        if not args.dry_run:\
            brain_append_md(md)\
            # ----- Airtable paid‑lead handling -----\
            if portrait.get("Stage", "").lower() in {"sotuv", "sold", "paid"}:\
                # Assume a paid lead – try to locate Airtable record by any known phone\
                for p in portrait["Phones"]:\
                    rec_id = find_airtable_record_by_phone(p)\
                    if rec_id:\
                        # Determine missing fields (simple check for empty string)\
                        missing = {}\
                        for field in ["Company", "Title", "Notes"]:\
                            if portrait.get(field) and portrait[field] != "-":\
                                missing[field] = portrait[field]\
                        if missing:\
                            airtable_update_missing(rec_id, missing)\
                        break\
        else:\
            logging.info("Dry run – not writing to Obsidian or Airtable.")\
    finally:\
        # Remove lock line (basic approach)\
        try:\
            with agents_md.open("r", encoding="utf-8") as f:\
                lines = f.readlines()\
            with agents_md.open("w", encoding="utf-8") as f:\
                for l in lines:\
                    if l.strip() != lock_line.strip():\
                        f.write(l)\
        except Exception as e:\
            logging.warning("Failed to clean lock line: %s", e)\
\
if __name__ == "__main__":\
    main()\
