"""Full amoCRM Migration & Multi-Seller Setup for Twenty CRM & Jon CRM.

1. Creates seller accounts in Twenty CRM:
   - Baxtiyorjon Gaziyev (Admin)
   - Shahnoza Abdijabborova (Seller)
   - Rayxona (Seller)
   - Mumtozmaxal (Seller)
   - Farangiz (Seller)
   - Oydin Ermuhammadova (Seller)
   Password for all sellers: JonSotuv2026! (can be changed in settings)

2. Fetches ALL 2,572 leads from amoCRM (Won 142, Lost 143, and all Active):
   - Contacts & Companies
   - Ingests into Twenty CRM PostgreSQL & crm_dialer.db SQLite
   - Correctly assigns each lead's ownerId to their respective seller
"""
from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("full_migration")

WORKSPACE_ID = "da90a5c2-0152-4cf2-b95b-b73b47100f3d"
APPLICATION_ID = "1b512fc9-f794-41aa-ba05-c3221144e9ef"
ADMIN_ROLE_ID = "61c56ad1-fee8-451c-aa01-8731ace21d61"
MEMBER_ROLE_ID = "ebd75afd-bc56-4db1-aa27-e6e1b0e4077a"
SCHEMA = "workspace_cxtozfktyq4bmf2sazl8s5zjx"

# Default bcrypt hash for 'JonSotuv2026!'
SELLER_PASSWORD_HASH = "$2b$10$56V3JM/WIGZWmdBNiNxyB.WEo5f4FQfZxedFPFOZqwpZoL5yJ5W4e"

SELLERS = [
    {
        "slug": "baxtiyorjon",
        "email": "baxtiyorjongaziyev@gmail.com",
        "first_name": "Baxtiyorjon",
        "last_name": "Gaziyev",
        "role": "Admin",
        "role_id": ADMIN_ROLE_ID,
    },
    {
        "slug": "shahnoza",
        "email": "shahnoza@jonbranding.uz",
        "first_name": "Shahnoza",
        "last_name": "Abdijabborova",
        "role": "Member",
        "role_id": MEMBER_ROLE_ID,
    },
    {
        "slug": "rayxona",
        "email": "rayxona@jonbranding.uz",
        "first_name": "Rayxona",
        "last_name": "Sotuv",
        "role": "Member",
        "role_id": MEMBER_ROLE_ID,
    },
    {
        "slug": "mumtozmaxal",
        "email": "mumtozmaxal@jonbranding.uz",
        "first_name": "Mumtozmaxal",
        "last_name": "Sotuv",
        "role": "Member",
        "role_id": MEMBER_ROLE_ID,
    },
    {
        "slug": "farangiz",
        "email": "farangiz@jonbranding.uz",
        "first_name": "Farangiz",
        "last_name": "Sotuv",
        "role": "Member",
        "role_id": MEMBER_ROLE_ID,
    },
    {
        "slug": "oydin",
        "email": "oydin@jonbranding.uz",
        "first_name": "Oydin",
        "last_name": "Ermuhammadova",
        "role": "Member",
        "role_id": MEMBER_ROLE_ID,
    },
]

def run_psql_file(sql_file: str) -> None:
    cmd = f"docker exec -i twenty-db-1 psql -U postgres -d default < {sql_file}"
    subprocess.check_call(cmd, shell=True)

def run_psql_query(sql: str) -> str:
    cmd = ["docker", "exec", "-i", "twenty-db-1", "psql", "-U", "postgres", "-d", "default", "-t", "-A", "-c", sql]
    return subprocess.check_output(cmd).decode("utf-8").strip()

def setup_sellers() -> Dict[str, str]:
    """Sets up all sellers in Twenty CRM and returns mapping: seller_slug -> workspaceMemberId."""
    logger.info("Setting up sellers in Twenty CRM...")
    member_map: Dict[str, str] = {}

    for s in SELLERS:
        email = s["email"].lower()
        # Check if core.user exists
        user_id = run_psql_query(f"SELECT id FROM core.user WHERE email = '{email}';")
        if not user_id:
            user_id = str(uuid.uuid4())
            sql = f"""
            INSERT INTO core.user (
                id, email, "firstName", "lastName", "isEmailVerified", "passwordHash",
                "canAccessFullAdminPanel", "canImpersonate", locale, "createdAt", "updatedAt"
            ) VALUES (
                '{user_id}', '{email}', '{s["first_name"]}', '{s["last_name"]}', true, '{SELLER_PASSWORD_HASH}',
                {'true' if s['role'] == 'Admin' else 'false'}, {'true' if s['role'] == 'Admin' else 'false'}, 'uz-UZ', NOW(), NOW()
            );
            """
            with open("/tmp/u.sql", "w") as f:
                f.write(sql)
            run_psql_file("/tmp/u.sql")
            logger.info("Created core.user for %s (%s)", s["first_name"], email)

        # Check userWorkspace
        uw_id = run_psql_query(f"SELECT id FROM core.\"userWorkspace\" WHERE \"userId\" = '{user_id}' AND \"workspaceId\" = '{WORKSPACE_ID}';")
        if not uw_id:
            uw_id = str(uuid.uuid4())
            sql = f"""
            INSERT INTO core."userWorkspace" (
                id, "userId", "workspaceId", locale, "createdAt", "updatedAt"
            ) VALUES (
                '{uw_id}', '{user_id}', '{WORKSPACE_ID}', 'uz-UZ', NOW(), NOW()
            );
            """
            with open("/tmp/uw.sql", "w") as f:
                f.write(sql)
            run_psql_file("/tmp/uw.sql")

        # Check roleTarget
        rt_id = run_psql_query(f"SELECT id FROM core.\"roleTarget\" WHERE \"userWorkspaceId\" = '{uw_id}';")
        if not rt_id:
            rt_id = str(uuid.uuid4())
            sql = f"""
            INSERT INTO core."roleTarget" (
                id, "workspaceId", "roleId", "userWorkspaceId", "universalIdentifier", "applicationId", "createdAt", "updatedAt"
            ) VALUES (
                '{rt_id}', '{WORKSPACE_ID}', '{s["role_id"]}', '{uw_id}', '{uw_id}', '{APPLICATION_ID}', NOW(), NOW()
            );
            """
            with open("/tmp/rt.sql", "w") as f:
                f.write(sql)
            run_psql_file("/tmp/rt.sql")

        # Check workspaceMember
        wm_id = run_psql_query(f"SELECT id FROM {SCHEMA}.\"workspaceMember\" WHERE \"userEmail\" = '{email}';")
        if not wm_id:
            wm_id = str(uuid.uuid4())
            sql = f"""
            INSERT INTO {SCHEMA}."workspaceMember" (
                id, "userId", "userEmail", "nameFirstName", "nameLastName", "jobTitle",
                "createdAt", "updatedAt", position, "colorScheme", locale
            ) VALUES (
                '{wm_id}', '{user_id}', '{email}', '{s["first_name"]}', '{s["last_name"]}', 'Sotuv menejeri',
                NOW(), NOW(), 0, 'System', 'uz-UZ'
            );
            """
            with open("/tmp/wm.sql", "w") as f:
                f.write(sql)
            run_psql_file("/tmp/wm.sql")
            logger.info("Created workspaceMember for %s (%s)", s["first_name"], wm_id)

        member_map[s["slug"]] = wm_id

    logger.info("All sellers configured in Twenty CRM: %s", member_map)
    return member_map

def resolve_seller_slug(tags: List[str], responsible_user_id: int) -> str:
    """Determine seller slug from tags or responsible_user_id."""
    tag_str = " ".join(tags).lower()
    if "rayxon" in tag_str:
        return "rayxona"
    if "mumtoz" in tag_str:
        return "mumtozmaxal"
    if "farangiz" in tag_str:
        return "farangiz"
    if "oydin" in tag_str or responsible_user_id in (13838466, 13841510):
        return "oydin"
    if "baxtiyor" in tag_str or responsible_user_id == 8128012:
        return "baxtiyorjon"
    # Default active sales rep
    return "shahnoza"

def fetch_all_amocrm_leads() -> List[Dict[str, Any]]:
    """Fetches all leads from amoCRM across all pages with contacts."""
    token_file = "data/amocrm_token.json"
    with open(token_file, "r", encoding="utf-8") as f:
        token = json.load(f)["access_token"]
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "JonBranding/1.0"}

    all_leads: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://jonbranding.amocrm.ru/api/v4/leads?limit=250&page={page}&with=contacts"
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200:
            logger.info("Reached end of leads at page %d (HTTP %s)", page, res.status_code)
            break
        data = res.json()
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            break
        all_leads.extend(leads)
        logger.info("Fetched page %d: %d leads (Total accumulated: %d)", page, len(leads), len(all_leads))
        if not data.get("_links", {}).get("next"):
            break
        page += 1
    return all_leads

def migrate_leads(leads: List[Dict[str, Any]], seller_map: Dict[str, str]) -> None:
    logger.info("Migrating %d leads into Twenty CRM & SQLite...", len(leads))

    # Prepare SQLite DialerStore
    dialer_conn = sqlite3.connect("/home/ubuntu/oisha-os/data/crm_dialer.db")
    dialer_c = dialer_conn.cursor()

    # Pre-load existing companies and people from Twenty CRM
    existing_comp_raw = run_psql_query(f"SELECT name, id FROM {SCHEMA}.company;")
    comp_map: Dict[str, str] = {}
    if existing_comp_raw:
        for line in existing_comp_raw.splitlines():
            if "|" in line:
                n, cid = line.split("|", 1)
                comp_map[n.strip().lower()] = cid.strip()

    existing_person_raw = run_psql_query(f"SELECT \"phonesPrimaryPhoneNumber\", id FROM {SCHEMA}.person;")
    person_map: Dict[str, str] = {}
    if existing_person_raw:
        for line in existing_person_raw.splitlines():
            if "|" in line:
                p, pid = line.split("|", 1)
                person_map[p.strip()] = pid.strip()

    # SQL batch file for Twenty CRM
    sql_statements: List[str] = []

    companies_to_insert: Dict[str, Tuple[str, str]] = {} # clean_name -> (id, safe_name)
    people_to_insert: Dict[str, Tuple[str, str, str, str]] = {} # phone -> (id, fname, lname, comp_id)

    total_won = 0
    total_lost = 0
    total_active = 0

    for l in leads:
        lid = int(l["id"])
        lname = (l.get("name") or f"Bitim #{lid}").strip().replace("'", "''")
        price = float(l.get("price") or 0.0)
        status_id = int(l.get("status_id") or 0)
        pipe_id = int(l.get("pipeline_id") or 11162698)
        created_at_ts = l.get("created_at") or int(time.time())
        created_at_iso = datetime.fromtimestamp(created_at_ts, tz=timezone.utc).isoformat()
        resp_user_id = int(l.get("responsible_user_id") or 13021974)

        raw_tags = [t.get("name") for t in (l.get("_embedded", {}).get("tags") or []) if t.get("name")]
        seller_slug = resolve_seller_slug(raw_tags, resp_user_id)
        owner_uuid = seller_map.get(seller_slug, seller_map.get("shahnoza"))

        # Stage mapping
        if status_id == 142:
            stage = "CUSTOMER"
            status_slug = "sotuv"
            total_won += 1
        elif status_id == 143:
            stage = "PROPOSAL"
            status_slug = "qiziqmadi"
            total_lost += 1
        elif status_id in (87609510, 89067962):
            stage = "NEW"
            status_slug = "yangi"
            total_active += 1
        elif status_id in (87609518, 87609522):
            stage = "SCREENING"
            status_slug = "qayta_aloqa"
            total_active += 1
        elif status_id in (87609526, 89380154):
            stage = "MEETING"
            status_slug = "uchrashuv"
            total_active += 1
        else:
            stage = "PROPOSAL"
            status_slug = "jarayonda"
            total_active += 1

        # Extract contact & company
        contacts = l.get("_embedded", {}).get("contacts", [])
        cname, cphone, company_name = "", "", ""

        # Extract custom fields
        for cf in l.get("custom_fields_values") or []:
            f_name = (cf.get("field_name") or "").lower()
            vals = cf.get("values") or []
            if vals and not company_name and any(k in f_name for k in ["kompaniya", "brend", "firma", "brand"]):
                company_name = str(vals[0].get("value") or "").strip()

        if contacts:
            c = contacts[0]
            cname = (c.get("name") or "").strip()
            # If lead name contains company or phone
            for cf in c.get("custom_fields_values") or []:
                if cf.get("field_code") == "PHONE":
                    vals = cf.get("values") or []
                    if vals:
                        cphone = str(vals[0].get("value") or "").strip()
                elif cf.get("field_code") == "EMAIL":
                    pass

        # Clean company
        comp_id = None
        if company_name and company_name.lower() not in ("none", "null", "-", "yo'q", "brending"):
            c_key = company_name.strip().lower()
            if c_key in comp_map:
                comp_id = comp_map[c_key]
            elif c_key not in companies_to_insert:
                comp_id = str(uuid.uuid4())
                companies_to_insert[c_key] = (comp_id, company_name.replace("'", "''"))
                comp_map[c_key] = comp_id
            else:
                comp_id = companies_to_insert[c_key][0]

        # Clean person
        person_id = None
        if cphone:
            if cphone in person_map:
                person_id = person_map[cphone]
            elif cphone not in people_to_insert:
                person_id = str(uuid.uuid4())
                parts = cname.split(" ", 1) if cname else ["Mijoz", ""]
                fname = parts[0].replace("'", "''")
                lname_part = (parts[1] if len(parts) > 1 else "").replace("'", "''")
                people_to_insert[cphone] = (person_id, fname, lname_part, comp_id or "")
                person_map[cphone] = person_id
            else:
                person_id = people_to_insert[cphone][0]

        # Insert into SQLite DialerStore
        tags_json = json.dumps(raw_tags, ensure_ascii=False)
        dialer_c.execute(
            """
            INSERT INTO dialer_leads (
                id, pipeline_id, name, contact_name, company_name, phone, price,
                status_id, status_slug, responsible_user_id, responsible_name, tags_json, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                price = excluded.price,
                status_id = excluded.status_id,
                status_slug = excluded.status_slug,
                is_active = excluded.is_active;
            """,
            (
                lid, pipe_id, l.get("name") or f"Bitim #{lid}", cname, company_name, cphone, price,
                status_id, status_slug, resp_user_id, seller_slug.title(), tags_json,
                0 if status_id in (142, 143) else 1
            )
        )

        # Build Twenty CRM opportunity upsert SQL
        opp_uuid = str(uuid.uuid4())
        micros = int(price * 1_000_000)
        safe_cname = cname.replace("'", "''")
        safe_comp = company_name.replace("'", "''")
        comp_clause = f"'{comp_id}'" if comp_id else "NULL"
        poc_clause = f"'{person_id}'" if person_id else "NULL"
        owner_clause = f"'{owner_uuid}'" if owner_uuid else "NULL"

        sql_opp = f"""
        INSERT INTO {SCHEMA}."opportunity" (
            id, name, "amountAmountMicros", "amountCurrencyCode", stage, "amoId",
            "companyId", "pointOfContactId", "ownerId", "amoStatusId", "statusSlug",
            "pipelineId", "responsibleUserId", "responsibleName", "contactName",
            "companyName", "contactPhone", "createdAt", "updatedAt", position
        ) VALUES (
            '{opp_uuid}', '{lname}', {micros}, 'UZS', '{stage}', {lid},
            {comp_clause}, {poc_clause}, {owner_clause}, {status_id}, '{status_slug}',
            {pipe_id}, {resp_user_id}, '{seller_slug.title()}', '{safe_cname}',
            '{safe_comp}', '{cphone}', '{created_at_iso}', NOW(), 0
        ) ON CONFLICT ("amoId") DO UPDATE SET
            name = excluded.name,
            "amountAmountMicros" = excluded."amountAmountMicros",
            stage = excluded.stage,
            "amoStatusId" = excluded."amoStatusId",
            "statusSlug" = excluded."statusSlug",
            "ownerId" = COALESCE(excluded."ownerId", {SCHEMA}."opportunity"."ownerId"),
            "companyId" = COALESCE(excluded."companyId", {SCHEMA}."opportunity"."companyId"),
            "pointOfContactId" = COALESCE(excluded."pointOfContactId", {SCHEMA}."opportunity"."pointOfContactId");
        """
        sql_statements.append(sql_opp)

    dialer_conn.commit()
    logger.info("Committed %d leads to SQLite crm_dialer.db", len(leads))

    # Insert new companies into Twenty CRM
    logger.info("Inserting %d new companies into Twenty CRM...", len(companies_to_insert))
    comp_sqls = []
    for c_key, (cid, sname) in companies_to_insert.items():
        comp_sqls.append(f"""
        INSERT INTO {SCHEMA}."company" (
            id, name, "createdAt", "updatedAt", position, "createdByName", "updatedByName"
        ) VALUES (
            '{cid}', '{sname}', NOW(), NOW(), 0, 'amoCRM Full Sync', 'amoCRM Full Sync'
        ) ON CONFLICT (id) DO NOTHING;
        """)

    with open("/tmp/comp_insert.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(comp_sqls))
    run_psql_file("/tmp/comp_insert.sql")

    # Insert new people into Twenty CRM
    logger.info("Inserting %d new people into Twenty CRM...", len(people_to_insert))
    people_sqls = []
    for phone, (pid, fname, lname_p, comp_id_p) in people_to_insert.items():
        comp_cl = f"'{comp_id_p}'" if comp_id_p else "NULL"
        people_sqls.append(f"""
        INSERT INTO {SCHEMA}."person" (
            id, "nameFirstName", "nameLastName", "phonesPrimaryPhoneNumber", "phonesPrimaryPhoneCallingCode",
            "companyId", "createdAt", "updatedAt", position, "createdByName", "updatedByName"
        ) VALUES (
            '{pid}', '{fname}', '{lname_p}', '{phone}', '+998',
            {comp_cl}, NOW(), NOW(), 0, 'amoCRM Full Sync', 'amoCRM Full Sync'
        ) ON CONFLICT (id) DO NOTHING;
        """)

    with open("/tmp/people_insert.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(people_sqls))
    run_psql_file("/tmp/people_insert.sql")

    # Run opportunity SQL batch (in chunks of 300 statements)
    logger.info("Executing %d opportunity upsert statements in Twenty CRM...", len(sql_statements))
    chunk_size = 300
    for i in range(0, len(sql_statements), chunk_size):
        chunk = sql_statements[i:i + chunk_size]
        chunk_file = f"/tmp/opp_chunk_{i}.sql"
        with open(chunk_file, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk))
        run_psql_file(chunk_file)
        logger.info("Executed opportunities chunk %d to %d...", i, i + len(chunk))

    logger.info("=== FULL MIGRATION SUCCESS ===")
    logger.info("Total Leads Migrated: %d", len(leads))
    logger.info("  Won (Status 142): %d", total_won)
    logger.info("  Lost (Status 143): %d", total_lost)
    logger.info("  Active Leads: %d", total_active)
    logger.info("Twenty DB Counts:")
    logger.info("  Total Opportunities: %s", run_psql_query(f"SELECT count(*) FROM {SCHEMA}.opportunity;"))
    logger.info("  Total Companies: %s", run_psql_query(f"SELECT count(*) FROM {SCHEMA}.company;"))
    logger.info("  Total People: %s", run_psql_query(f"SELECT count(*) FROM {SCHEMA}.person;"))

if __name__ == "__main__":
    seller_map = setup_sellers()
    leads = fetch_all_amocrm_leads()
    migrate_leads(leads, seller_map)
