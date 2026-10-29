import json
import os
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

with open("data/amocrm_token.json", encoding="utf-8") as f:
    token = json.load(f)["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# 1. Get drive url
r_acc = requests.get("https://jonbranding.amocrm.ru/api/v4/account?with=drive_url", headers=headers, timeout=10)
drive_url = r_acc.json().get("drive_url")
print(f"Drive URL: {drive_url}")

file_path = "data/utc_recordings/cmuhzvpb30kj6l6gqwph3brc3.mp3"
file_name = "UTC_Suhbat_Card135_Mirzohidjon.mp3"
file_size = os.path.getsize(file_path)

print(f"Uploading {file_name} ({file_size} bytes)...")

# 2. Create session
session_payload = {
    "file_name": file_name,
    "file_size": file_size
}
session_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
r_sess = requests.post(f"{drive_url}/v1.0/sessions", headers=session_headers, json=session_payload, timeout=15)
print(f"Session response status: {r_sess.status_code}")
sess_data = r_sess.json()
upload_url = sess_data["upload_url"]
max_part = sess_data.get("max_part_size", 524288)

print(f"Upload URL: {upload_url[:50]}..., Max part: {max_part}")

# 3. Upload chunks
uploaded_info = None
with open(file_path, "rb") as f:
    part_num = 1
    while True:
        chunk = f.read(max_part)
        if not chunk:
            break
        part_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"
        }
        r_part = requests.post(upload_url, data=chunk, headers=part_headers, timeout=30)
        if r_part.status_code not in (200, 201, 202):
            print(f"Part {part_num} failed: {r_part.status_code} {r_part.text}")
            break
        res = r_part.json()
        if "uuid" in res:
            uploaded_info = res
            print(f"Upload complete! File UUID: {res['uuid']}")
            break
        elif "next_url" in res:
            upload_url = res["next_url"]
        elif "upload_url" in res:
            upload_url = res["upload_url"]
        part_num += 1

if uploaded_info:
    file_uuid = uploaded_info["uuid"]
    # 4. Attach file to lead 53259529
    lead_id = 53259529
    attach_url = f"https://jonbranding.amocrm.ru/api/v4/leads/{lead_id}/files"
    r_attach = requests.post(attach_url, headers=session_headers, json=[{"file_uuid": file_uuid}], timeout=15)
    print(f"Attach response: {r_attach.status_code} {r_attach.text}")
