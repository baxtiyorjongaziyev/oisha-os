"""Consolidate PRESALES + CLOSER + Target LEADs into one "Sotuv" pipeline.

UTC, Farmer, QC, Reactivation, Partnership and HR pipelines are untouched.
Only OPEN leads are moved; closed (142/143) leads stay for history.

Usage:
    python scripts/amocrm_consolidate_sales.py            # dry-run
    python scripts/amocrm_consolidate_sales.py --apply    # execute

Reads the long-lived token from data/amocrm_token.json and never refreshes it
(refreshing locally would invalidate the Oracle-owned token).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_ROOT = ROOT if (ROOT / "data" / "amocrm_token.json").exists() else ROOT.parents[2]

SALES = 11162698  # 1. PRESALES -> "Sotuv"
CLOSER = 11162702
TARGET = 11295630

# Existing PRESALES statuses renamed to the agreed names
RENAME = {
    87609514: "Yangi",
    87609518: "Aloqa",
    87609522: "Kvalifikatsiya",
    87609526: "Uchrashuv",
}
NEW_STATUSES = [("KP", 50, "#fffd7f"), ("Muzokara", 60, "#98cbff"), ("Avans kutilmoqda", 70, "#ffce5a")]
SORT = {87609514: 10, 87609518: 20, 87609522: 30, 87609526: 40}

# old status id -> target status NAME in Sotuv
CLOSER_MAP = {
    87609530: "Yangi",  # Неразобранное
    87609534: "Uchrashuv",  # Uchrashuv o'tdi
    87609538: "KP",
    87609542: "Muzokara",
    87609546: "Avans kutilmoqda",  # Shartnoma tayyorlanmoqda
    87609550: "Avans kutilmoqda",
}
TARGET_MAP = {
    88564634: "Yangi",  # Неразобранное
    88696194: "Yangi",  # Yangi murojaat
    88564638: "Aloqa",
    88564642: "Kvalifikatsiya",
    88564646: "Uchrashuv",
    88564682: "KP",  # Taklif berildi
    88564686: "Muzokara",  # Qaror kutilmoqda
}
LEAD_SOURCE_FIELD = "Lead manbasi"
TARGET_SOURCE_VALUE = "Target"


def _env(name: str) -> str:
    for line in (MAIN_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit(f"{name} missing in .env")


TOKEN = json.loads((MAIN_ROOT / "data" / "amocrm_token.json").read_text())["access_token"]
SUB = _env("AMOCRM_SUBDOMAIN")
BASE = f"https://{SUB}/api/v4" if "." in SUB else f"https://{SUB}.amocrm.ru/api/v4"


def api(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} -> {exc.code}: {exc.read().decode()[:800]}")
    time.sleep(0.2)
    return json.loads(raw) if raw else {}


def leads_in(pipeline_id: int) -> list[dict]:
    out, page = [], 1
    while True:
        d = api("GET", f"/leads?limit=250&page={page}&filter[pipeline_id][]={pipeline_id}")
        batch = d.get("_embedded", {}).get("leads", []) if d else []
        out += batch
        if len(batch) < 250:
            return out
        page += 1


def main() -> None:
    apply = "--apply" in sys.argv
    pipes = {p["id"]: p for p in api("GET", "/leads/pipelines")["_embedded"]["pipelines"]}
    sales_statuses = {s["id"]: s["name"] for s in pipes[SALES]["_embedded"]["statuses"]}

    fields = api("GET", "/leads/custom_fields?limit=250")["_embedded"]["custom_fields"]
    src_field = next((f for f in fields if f["name"] == LEAD_SOURCE_FIELD), None)
    src_enum = None
    if src_field:
        src_enum = next((e["id"] for e in src_field.get("enums") or [] if e["value"] == TARGET_SOURCE_VALUE), None)
        print(f"'{LEAD_SOURCE_FIELD}' options:", [e["value"] for e in src_field.get("enums") or []])

    moves = []
    for pid, mapping in ((CLOSER, CLOSER_MAP), (TARGET, TARGET_MAP)):
        for lead in leads_in(pid):
            if lead["status_id"] in (142, 143):
                continue
            moves.append((lead, pid, mapping.get(lead["status_id"], "Yangi")))

    backup_path = MAIN_ROOT / "data" / f"amocrm_consolidate_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
    print(f"Open leads to move: {len(moves)} (CLOSER {sum(m[1]==CLOSER for m in moves)}, TARGET {sum(m[1]==TARGET for m in moves)})")
    from collections import Counter
    print("Target stages:", dict(Counter(m[2] for m in moves)))
    if not apply:
        print("DRY-RUN. Re-run with --apply to execute.")
        return

    backup_path.write_text(json.dumps([m[0] for m in moves], ensure_ascii=False), encoding="utf-8")
    print("Backup:", backup_path)

    # 1. Rename pipeline + statuses
    api("PATCH", f"/leads/pipelines/{SALES}", {"name": "Sotuv"})
    for sid, name in RENAME.items():
        api("PATCH", f"/leads/pipelines/{SALES}/statuses/{sid}", {"name": name, "sort": SORT[sid]})
    # 2. Add missing statuses
    existing = {name: sid for sid, name in {**sales_statuses, **RENAME}.items()}
    to_add = [{"name": n, "sort": s, "color": c} for n, s, c in NEW_STATUSES if n not in existing]
    if to_add:
        res = api("POST", f"/leads/pipelines/{SALES}/statuses", to_add)
        for s in res["_embedded"]["statuses"]:
            existing[s["name"]] = s["id"]
    print("Sotuv statuses:", existing)

    # 3. Move leads in batches of 50
    for i in range(0, len(moves), 50):
        chunk = []
        for lead, pid, target_name in moves[i : i + 50]:
            item = {"id": lead["id"], "pipeline_id": SALES, "status_id": existing[target_name]}
            if pid == TARGET and src_field and src_enum:
                item["custom_fields_values"] = [{"field_id": src_field["id"], "values": [{"enum_id": src_enum}]}]
            chunk.append(item)
        api("PATCH", "/leads", chunk)
        print(f"moved {i + len(chunk)}/{len(moves)}")

    # 4. Mark emptied pipelines as archive (closed leads remain there)
    for pid in (CLOSER, TARGET):
        name = pipes[pid]["name"]
        if not name.startswith("[ARXIV]"):
            api("PATCH", f"/leads/pipelines/{pid}", {"name": f"[ARXIV] {name}"})
    print("Done.")


if __name__ == "__main__":
    main()
