"""
Align Sales Pipeline (Sotuv Bo'limi) to 5 Clean Stages:
1. Yangi
2. Aloqa
3. Kvalifikatsiya
4. Uchrashuv
5. Kelishuv / Yopish

Merges 'KP' (88871062) and 'Avans kutilmoqda' (88871070) into 'Kelishuv / Yopish' (88871066).
Creates full backup before mutation.
Rule 6 compliant: <= 400 LOC.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PipelineAligner")

SALES_PIPELINE_ID = 11162698
STATUS_YANGI = 87609514
STATUS_ALOQA = 87609518
STATUS_KVALIFIKATSIYA = 87609522
STATUS_UCHRASHUV = 87609526
STATUS_KELISHUV_YOPISH = 88871066
STATUS_KP_OLD = 88871062
STATUS_AVANS_OLD = 88871070
LEGACY_TARGET_ARXIV_PIPELINE = 11295630

TOKEN_FILE = _ROOT / "data" / "amocrm_token.json"
BACKUP_FILE = _ROOT / "data" / "backup_sales_pipeline_before_5_stages.json"


def get_token() -> str:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)["access_token"]


def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fetch_pipeline_leads(token: str, pipeline_id: int) -> List[dict]:
    headers = get_headers(token)
    leads = []
    page = 1
    while page <= 20:
        url = f"https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]={pipeline_id}&limit=250&page={page}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            break
        items = resp.json().get("_embedded", {}).get("leads", [])
        if not items:
            break
        leads.extend(items)
        if len(items) < 250:
            break
        page += 1
    return leads


def backup_pipeline(leads: List[dict]) -> None:
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)
    logger.info(f"Backup saved: {len(leads)} leads -> {BACKUP_FILE}")


def move_leads_to_status(token: str, lead_ids: List[int], target_status_id: int, target_pipeline_id: int = SALES_PIPELINE_ID) -> int:
    if not lead_ids:
        return 0
    headers = get_headers(token)
    updated = 0
    # AmoCRM accepts batches up to 250 in PATCH /api/v4/leads
    for i in range(0, len(lead_ids), 50):
        batch = lead_ids[i:i + 50]
        payload = [{"id": lid, "status_id": target_status_id, "pipeline_id": target_pipeline_id} for lid in batch]
        resp = requests.patch("https://jonbranding.amocrm.ru/api/v4/leads", headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 204):
            updated += len(batch)
            logger.info(f"Successfully moved {len(batch)} leads -> Status {target_status_id}")
        else:
            logger.error(f"Failed to move batch: HTTP {resp.status_code} - {resp.text}")
    return updated


def move_archived_lead(token: str) -> None:
    """Move any dangling lead from archived pipeline to Sotuv -> Yangi."""
    headers = get_headers(token)
    resp = requests.get(f"https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]={LEGACY_TARGET_ARXIV_PIPELINE}", headers=headers, timeout=15)
    if resp.status_code == 200:
        leads = resp.json().get("_embedded", {}).get("leads", [])
        if leads:
            for l in leads:
                if l["status_id"] not in (142, 143):
                    logger.info(f"Moving dangling lead {l['id']} ('{l.get('name')}') from Arxiv -> Sotuv Bo'limi (Yangi)...")
                    move_leads_to_status(token, [l["id"]], STATUS_YANGI, SALES_PIPELINE_ID)


def update_pipeline_stages(token: str) -> bool:
    headers = get_headers(token)
    # Target 5 statuses for Sotuv Bo'limi
    payload = {
        "name": "Sotuv Bo'limi",
        "_embedded": {
            "statuses": [
                {"id": STATUS_YANGI, "name": "Yangi", "sort": 10, "color": "#fffeb2"},
                {"id": STATUS_ALOQA, "name": "Aloqa", "sort": 20, "color": "#38bdf8"},
                {"id": STATUS_KVALIFIKATSIYA, "name": "Kvalifikatsiya", "sort": 30, "color": "#a855f7"},
                {"id": STATUS_UCHRASHUV, "name": "Uchrashuv", "sort": 40, "color": "#10b981"},
                {"id": STATUS_KELISHUV_YOPISH, "name": "Kelishuv / Yopish", "sort": 50, "color": "#3b82f6"},
            ]
        }
    }
    url = f"https://jonbranding.amocrm.ru/api/v4/leads/pipelines/{SALES_PIPELINE_ID}"
    resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    if resp.status_code in (200, 204):
        logger.info("Pipeline statuses successfully updated to 5 clean stages!")
        return True
    else:
        logger.error(f"Failed to update pipeline stages: HTTP {resp.status_code} - {resp.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Align AmoCRM Sales Pipeline to 5 Stages")
    parser.add_argument("--live", action="store_true", help="Execute real migration in AmoCRM")
    args = parser.parse_args()

    token = get_token()
    logger.info("Fetching current leads from Sotuv Bo'limi...")
    leads = fetch_pipeline_leads(token, SALES_PIPELINE_ID)
    logger.info(f"Total leads in Sotuv Bo'limi: {len(leads)}")

    # Classify leads by status
    kp_leads = [l["id"] for l in leads if l["status_id"] == STATUS_KP_OLD]
    avans_leads = [l["id"] for l in leads if l["status_id"] == STATUS_AVANS_OLD]
    closing_leads = [l["id"] for l in leads if l["status_id"] == STATUS_KELISHUV_YOPISH]

    logger.info(f"Current distribution:")
    logger.info(f" - KP (88871062): {len(kp_leads)} leads")
    logger.info(f" - Muzokara / Kelishuv (88871066): {len(closing_leads)} leads")
    logger.info(f" - Avans kutilmoqda (88871070): {len(avans_leads)} leads")
    logger.info(f"Target 'Kelishuv / Yopish' total will be: {len(kp_leads) + len(closing_leads) + len(avans_leads)} leads")

    if not args.live:
        logger.info("[DRY-RUN] No changes made. Run with --live to execute migration.")
        return

    # 1. Backup
    backup_pipeline(leads)

    # 2. Move KP leads -> Muzokara / Kelishuv
    if kp_leads:
        logger.info(f"Moving {len(kp_leads)} leads from KP -> Kelishuv / Yopish...")
        move_leads_to_status(token, kp_leads, STATUS_KELISHUV_YOPISH)

    # 3. Move Avans leads -> Muzokara / Kelishuv
    if avans_leads:
        logger.info(f"Moving {len(avans_leads)} leads from Avans -> Kelishuv / Yopish...")
        move_leads_to_status(token, avans_leads, STATUS_KELISHUV_YOPISH)

    # 4. Move dangling archived lead if any
    move_archived_lead(token)

    # 5. Update Pipeline Stages to 5 clean stages
    logger.info("Updating pipeline structure in AmoCRM...")
    time.sleep(1)
    ok = update_pipeline_stages(token)
    if ok:
        logger.info("MIGRATION COMPLETED SUCCESSFULLY! 🎉")
    else:
        logger.error("Pipeline structure update had an error, please inspect logs.")


if __name__ == "__main__":
    main()
