"""
Upload UTC Call Audio Recordings to amoCRM Lead Cards.

Iterates through all 30 high-priority leads imported into amoCRM,
uploads their real MP3 call recordings to amoCRM Drive in chunks,
and binds each audio recording as a native attachment note in the lead feed.

Usage:
    python scripts/upload_audio_to_amocrm_leads.py --dry-run
    python scripts/upload_audio_to_amocrm_leads.py --live
    python scripts/upload_audio_to_amocrm_leads.py --live --limit 5
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AmoCRM_Audio_Uploader")

ROOT_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT_DIR / "data" / "amocrm_token.json"
UTC_SESSION_FILE = ROOT_DIR / "data" / "utc_session.json"
CACHE_FILE = ROOT_DIR / "data" / "utc_cache" / "leads_with_recordings.json"
RECORDINGS_DIR = ROOT_DIR / "data" / "utc_recordings"
AUDIT_LOG_FILE = ROOT_DIR / "data" / "amocrm_uploaded_audios.json"

BASE_URL = "https://jonbranding.amocrm.ru"

TARGET_LEADS: List[Dict[str, Any]] = [
    {"card_no": 135, "lead_id": 53259529, "name": "Mirzohidjon", "phone": "998914797722"},
    {"card_no": 81, "lead_id": 53259563, "name": "Farrux", "phone": "998911881199"},
    {"card_no": 113, "lead_id": 53259565, "name": "Abdumalik", "phone": "998905550805"},
    {"card_no": 143, "lead_id": 53259649, "name": "Дусназарова Нафиса", "phone": "998997620066"},
    {"card_no": 214, "lead_id": 53259743, "name": "Абдували", "phone": "998973852929"},
    {"card_no": 339, "lead_id": 52830739, "name": "Akmaljon", "phone": "998907011001"},
    {"card_no": 78, "lead_id": 53259811, "name": "Мансуржон", "phone": "998912893030"},
    {"card_no": 133, "lead_id": 53259815, "name": "Azamat", "phone": "998973028384"},
    {"card_no": 206, "lead_id": 52392311, "name": "Hilola", "phone": "998990089908"},
    {"card_no": 328, "lead_id": 52819189, "name": "Durdona", "phone": "998983143444"},
    {"card_no": 265, "lead_id": 52698365, "name": "Akmal", "phone": "998998010899"},
    {"card_no": 120, "lead_id": 53259821, "name": "Begzod", "phone": "998770147703"},
    {"card_no": 157, "lead_id": 53259827, "name": "Abdulloh", "phone": "998771400202"},
    {"card_no": 88, "lead_id": 53259829, "name": "Izzatillo", "phone": "998907797710"},
    {"card_no": 142, "lead_id": 53259831, "name": "Maxfirat", "phone": "998977157877"},
    {"card_no": 159, "lead_id": 53259837, "name": "Islam", "phone": "998772019393"},
    {"card_no": 184, "lead_id": 53259839, "name": "Xikmatjon", "phone": "998881250110"},
    {"card_no": 58, "lead_id": 53259843, "name": "Umid", "phone": "998940097921"},
    {"card_no": 65, "lead_id": 53259847, "name": "Oybek", "phone": "998939239333"},
    {"card_no": 6, "lead_id": 53259849, "name": "Farhod Shaymardanov", "phone": "998997736306"},
    {"card_no": 111, "lead_id": 53259853, "name": "Сугдиёна", "phone": "998934448414"},
    {"card_no": 23, "lead_id": 53259857, "name": "Iqboljon Pol shlipovka", "phone": "998911085058"},
    {"card_no": 216, "lead_id": 53259861, "name": "Sardor", "phone": "998978710208"},
    {"card_no": 175, "lead_id": 53259865, "name": "Abdushukur", "phone": "998999085112"},
    {"card_no": 208, "lead_id": 53259871, "name": "Diyorbek", "phone": "998701123244"},
    {"card_no": 42, "lead_id": 53259877, "name": "Shohruh", "phone": "998911151133"},
    {"card_no": 309, "lead_id": 49146643, "name": "Muhammadjon Ne'matov", "phone": "998775174949"},
    {"card_no": 98, "lead_id": 53259883, "name": "Murodxon", "phone": "998700500501"},
    {"card_no": 325, "lead_id": 52816839, "name": "Suxrob", "phone": "998972624100"},
    {"card_no": 30, "lead_id": 53259887, "name": "Baxtiyorjon Nabiyev", "phone": "998934834777"}
]


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-_]", "_", name.strip())
    return re.sub(r"_+", "_", cleaned).strip("_")


def get_amocrm_token() -> str:
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)["access_token"]


def get_drive_url(token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/v4/account?with=drive_url", headers=headers, timeout=10)
    drive_url = r.json().get("drive_url")
    if not drive_url:
        raise RuntimeError("Failed to retrieve drive_url from amoCRM account")
    return drive_url


def ensure_utc_recording(rec_id: str) -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = RECORDINGS_DIR / f"{rec_id}.mp3"
    if target_path.exists() and target_path.stat().st_size > 1000:
        return target_path

    with open(UTC_SESSION_FILE, encoding="utf-8") as f:
        sess = json.load(f)
    headers = {
        "Authorization": f"Bearer {sess['token']}",
        "x-company-id": sess.get("company", "company_default"),
        "Accept": "application/json"
    }
    url = f"https://sales.kontaktmarkazi.com/api/recordings/{rec_id}/file"
    r = requests.get(url, headers=headers, timeout=45)
    if r.status_code == 200 and len(r.content) > 1000:
        with open(target_path, "wb") as f:
            f.write(r.content)
        return target_path
    raise RuntimeError(f"Could not download recording {rec_id} from UTC: {r.status_code}")


def upload_chunks(drive_url: str, token: str, file_path: Path, display_name: str) -> Tuple[str, str]:
    file_size = file_path.stat().st_size
    sess_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sess_payload = {"file_name": display_name, "file_size": file_size}
    r_sess = requests.post(f"{drive_url}/v1.0/sessions", headers=sess_headers, json=sess_payload, timeout=15)
    if r_sess.status_code != 200:
        raise RuntimeError(f"Drive session creation failed: {r_sess.status_code} {r_sess.text}")
    
    sess_data = r_sess.json()
    upload_url = sess_data["upload_url"]
    max_part = sess_data.get("max_part_size", 524288)

    file_uuid = None
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(max_part)
            if not chunk:
                break
            part_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}
            r_part = requests.post(upload_url, data=chunk, headers=part_headers, timeout=30)
            if r_part.status_code not in (200, 201, 202):
                raise RuntimeError(f"Upload chunk failed: {r_part.status_code} {r_part.text}")
            res = r_part.json()
            if "uuid" in res:
                file_uuid = res["uuid"]
                break
            upload_url = res.get("next_url") or res.get("upload_url")
            time.sleep(0.05)

    if not file_uuid:
        raise RuntimeError(f"File upload did not return uuid for {display_name}")

    # Fetch version_uuid
    r_meta = requests.get(f"{drive_url}/v1.0/files/{file_uuid}", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    meta = r_meta.json()
    version_uuid = meta.get("version_uuid") or file_uuid
    return file_uuid, version_uuid


def attach_audio_to_lead(token: str, lead_id: int, file_uuid: str, version_uuid: str, file_name: str) -> bool:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = [{
        "note_type": "attachment",
        "params": {
            "file_uuid": file_uuid,
            "version_uuid": version_uuid,
            "file_name": file_name
        }
    }]
    url = f"{BASE_URL}/api/v4/leads/{lead_id}/notes"
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    return r.status_code in (200, 201)


def get_lead_attachment_names(token: str, lead_id: int) -> set[str]:
    headers = {"Authorization": f"Bearer {token}"}
    names = set()
    try:
        r = requests.get(f"{BASE_URL}/api/v4/leads/{lead_id}/notes?filter[note_type]=attachment", headers=headers, timeout=10)
        if r.status_code == 200:
            notes = r.json().get("_embedded", {}).get("notes", [])
            for n in notes:
                fn = n.get("params", {}).get("file_name")
                if fn:
                    names.add(fn)
    except Exception as e:
        logger.warning(f"Could not fetch existing attachments for lead {lead_id}: {e}")
    return names


def load_card_recordings_map() -> Dict[int, List[Dict[str, Any]]]:
    with open(CACHE_FILE, encoding="utf-8") as f:
        cache = json.load(f)
    result = {}
    for item in cache:
        cno = item.get("lead", {}).get("cardNo")
        if cno:
            seen = set()
            clean_recs = []
            for r in item.get("recordings", []):
                rid = r.get("recording_id")
                if rid and rid not in seen:
                    seen.add(rid)
                    clean_recs.append(r)
            clean_recs.sort(key=lambda x: x.get("created_at") or "")
            result[cno] = clean_recs
    return result


def main():
    parser = argparse.ArgumentParser(description="Upload UTC Call Recordings to amoCRM Lead Cards")
    parser.add_argument("--live", action="store_true", help="Perform live upload and attachment")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying")
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of leads to process")
    args = parser.parse_args()

    token = get_amocrm_token()
    drive_url = get_drive_url(token)
    card_map = load_card_recordings_map()

    selected_leads = TARGET_LEADS[:args.limit]
    total_audios = sum(len(card_map.get(l["card_no"], [])) for l in selected_leads)

    print("=" * 60)
    print(f"🎙️  AMO CRM AUDIO UPLOADER: {len(selected_leads)} TA LID | {total_audios} TA SUHBAT")
    print("=" * 60)

    if not args.live:
        print("\n[DRY RUN REJIMI]: AmoCRM'ga fayl yuklanmaydi.")
        for idx, l in enumerate(selected_leads, 1):
            recs = card_map.get(l["card_no"], [])
            print(f"{idx:2d}. Card #{l['card_no']:3d} | {l['name']:20s} -> Lead #{l['lead_id']} ({len(recs)} recordings)")
        print("\nIshga tushirish uchun: python scripts/upload_audio_to_amocrm_leads.py --live")
        return

    print("\n🚀 AUDIOLARNI AMOCRM'GA LIVE YUKLASH BOSHLANMOQDA...")
    uploaded_records = []
    success_leads = 0
    total_uploaded_audios = 0

    for idx, l in enumerate(selected_leads, 1):
        cno = l["card_no"]
        lid = l["lead_id"]
        cname = l["name"]
        sanitized_cname = sanitize_filename(cname)
        recs = card_map.get(cno, [])

        print(f"\n[{idx}/{len(selected_leads)}] Card #{cno} - {cname} (Lead #{lid}) | {len(recs)} ta audio:")
        existing_attachments = get_lead_attachment_names(token, lid)

        lead_audio_count = 0
        for part_idx, r in enumerate(recs, 1):
            rid = r.get("recording_id")
            dur = r.get("duration_sec", 0)
            m = dur // 60
            s = dur % 60
            display_name = f"UTC_Card_{cno}_{sanitized_cname}_Call{part_idx}_{m}m{s}s.mp3"

            # Check if duplicate or already attached
            if any(display_name.lower() in existing.lower() for existing in existing_attachments):
                print(f"   ↷ [{part_idx}/{len(recs)}] {display_name} allaqachon biriktirilgan (Skip)")
                lead_audio_count += 1
                continue

            try:
                local_file = ensure_utc_recording(rid)
                fsize_kb = local_file.stat().st_size // 1024
                print(f"   ⬆️  [{part_idx}/{len(recs)}] Yuklanmoqda: {display_name} ({fsize_kb} KB)...", end=" ", flush=True)

                file_uuid, version_uuid = upload_chunks(drive_url, token, local_file, display_name)
                time.sleep(0.2)

                ok = attach_audio_to_lead(token, lid, file_uuid, version_uuid, display_name)
                if ok:
                    print(f"✓ Biriktirildi! (UUID: {file_uuid[:8]}...)")
                    lead_audio_count += 1
                    total_uploaded_audios += 1
                    uploaded_records.append({
                        "card_no": cno,
                        "lead_id": lid,
                        "client_name": cname,
                        "file_name": display_name,
                        "file_uuid": file_uuid,
                        "version_uuid": version_uuid,
                        "duration_sec": dur
                    })
                else:
                    print("✗ Attach xato bo'ldi!")
                time.sleep(0.3)
            except Exception as e:
                print(f"✗ Xatolik: {e}")

        if lead_audio_count > 0:
            success_leads += 1

    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(uploaded_records, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("🎉 BARCHA SUHBATLAR AMOCRM KARTALARIGA MUVAFFAQISATLI YUKLANDI!")
    print(f"• Qamrab olingan lidlar: {success_leads} / {len(selected_leads)} ta")
    print(f"• Yuklangan va biriktirilgan audio fayllar: {total_uploaded_audios} ta")
    print(f"• Audit jurnali: {AUDIT_LOG_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
