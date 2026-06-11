"""Read-only live audit of the AmoCRM account.

Collects: pipelines/statuses, lead distribution, stale leads, open/overdue
tasks, duplicate tasks, leads without next action. GET requests only —
nothing is modified. Run on the Oracle VM where data/amocrm_token.json holds
the canonical token chain.
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.settings import settings  # noqa: E402
from src.services.core.amocrm_sync import AmoCRMSync  # noqa: E402

import requests  # noqa: E402

NOW = int(time.time())
DAY = 86400
MAX_PAGES = 12  # 250/page → up to 3000 entities per collection


def mask_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 7:
        return "***"
    return f"{digits[:5]}***{digits[-2:]}"


class AmoAuditor:
    def __init__(self) -> None:
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else ""
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.amo.base_url}{path}"
        resp = requests.get(url, headers=self.amo._get_headers(), params=params or {}, timeout=30)
        if resp.status_code == 401 and self.amo.refresh_token():
            resp = requests.get(url, headers=self.amo._get_headers(), params=params or {}, timeout=30)
        if resp.status_code == 204:
            return {}
        if resp.status_code != 200:
            print(f"  !! GET {path} → HTTP {resp.status_code}")
            return {}
        return resp.json()

    def get_all(self, path: str, params: dict | None = None, key: str = "") -> list[dict]:
        items: list[dict] = []
        page = 1
        while page <= MAX_PAGES:
            merged = dict(params or {})
            merged.update({"page": page, "limit": 250})
            data = self.get(path, merged)
            chunk = data.get("_embedded", {}).get(key, [])
            if not chunk:
                break
            items.extend(chunk)
            if len(chunk) < 250:
                break
            page += 1
        return items

    # ---------- sections ----------

    def audit_account(self) -> None:
        data = self.get("/api/v4/account", {"with": "users_groups,task_types"})
        print("=" * 70)
        print("1. AKKAUNT")
        print("=" * 70)
        print(f"  Nomi: {data.get('name')}  |  ID: {data.get('id')}")
        print(f"  Subdomain: {data.get('subdomain')}  |  Timezone: {data.get('timezone')}")

    def audit_users(self) -> dict[int, str]:
        users = self.get_all("/api/v4/users", key="users")
        print("\n" + "=" * 70)
        print("2. FOYDALANUVCHILAR")
        print("=" * 70)
        user_map: dict[int, str] = {}
        for u in users:
            user_map[u["id"]] = u.get("name", str(u["id"]))
            active = "aktiv" if u.get("rights", {}).get("is_active", True) else "OCHIRILGAN"
            print(f"  [{u['id']}] {u.get('name')}  ({active})")
        return user_map

    def audit_pipelines(self) -> dict[int, dict]:
        data = self.get("/api/v4/leads/pipelines")
        pipelines = data.get("_embedded", {}).get("pipelines", [])
        print("\n" + "=" * 70)
        print("3. VORONKALAR (PIPELINES)")
        print("=" * 70)
        pipe_map: dict[int, dict] = {}
        for p in pipelines:
            statuses = p.get("_embedded", {}).get("statuses", [])
            status_map = {s["id"]: s["name"] for s in statuses}
            pipe_map[p["id"]] = {"name": p["name"], "statuses": status_map}
            print(f"\n  Voronka: {p['name']} (id={p['id']}, {'ASOSIY' if p.get('is_main') else 'qoshimcha'})")
            for s in statuses:
                print(f"    - [{s['id']}] {s['name']}")
        return pipe_map

    def audit_leads(self, pipe_map: dict, user_map: dict) -> list[dict]:
        leads = self.get_all("/api/v4/leads", {"with": "contacts"}, key="leads")
        print("\n" + "=" * 70)
        print(f"4. BITIMLAR (LEADS) — jami yuklandi: {len(leads)}")
        print("=" * 70)

        by_status: Counter = Counter()
        by_user: Counter = Counter()
        stale_7d, stale_14d, stale_30d = [], [], []
        zero_price = 0
        no_contact = 0

        for lead in leads:
            pid = lead.get("pipeline_id")
            sid = lead.get("status_id")
            pname = pipe_map.get(pid, {}).get("name", str(pid))
            sname = pipe_map.get(pid, {}).get("statuses", {}).get(sid, str(sid))
            by_status[f"{pname} → {sname}"] += 1
            by_user[user_map.get(lead.get("responsible_user_id"), "?")] += 1

            if not lead.get("price"):
                zero_price += 1
            contacts = lead.get("_embedded", {}).get("contacts", [])
            if not contacts:
                no_contact += 1

            updated = lead.get("updated_at", 0)
            age_days = (NOW - updated) / DAY if updated else 999
            # 142/143 = won/lost system statuses — skip closed leads for staleness
            if sid not in (142, 143):
                entry = (lead["id"], lead.get("name", "")[:40], int(age_days), sname)
                if age_days > 30:
                    stale_30d.append(entry)
                elif age_days > 14:
                    stale_14d.append(entry)
                elif age_days > 7:
                    stale_7d.append(entry)

        print("\n  Status bo'yicha taqsimot:")
        for label, count in by_status.most_common():
            print(f"    {count:4d}  {label}")

        print("\n  Mas'ul bo'yicha taqsimot:")
        for label, count in by_user.most_common():
            print(f"    {count:4d}  {label}")

        print(f"\n  Narxsiz (price=0) bitimlar: {zero_price}")
        print(f"  Kontaktsiz bitimlar: {no_contact}")

        print(f"\n  QOTIB QOLGAN ochiq bitimlar (yangilanmagan):")
        print(f"    >30 kun: {len(stale_30d)} ta")
        for lid, name, age, st in stale_30d[:15]:
            print(f"      [{lid}] {name}  ({age} kun, status: {st})")
        print(f"    15-30 kun: {len(stale_14d)} ta")
        for lid, name, age, st in stale_14d[:10]:
            print(f"      [{lid}] {name}  ({age} kun, status: {st})")
        print(f"    8-14 kun: {len(stale_7d)} ta")

        return leads

    def audit_tasks(self, leads: list[dict], user_map: dict) -> None:
        open_tasks = self.get_all("/api/v4/tasks", {"filter[is_completed]": 0}, key="tasks")
        print("\n" + "=" * 70)
        print(f"5. OCHIQ VAZIFALAR — jami: {len(open_tasks)}")
        print("=" * 70)

        overdue = []
        by_user: Counter = Counter()
        per_lead: dict[int, list[str]] = defaultdict(list)

        for t in open_tasks:
            by_user[user_map.get(t.get("responsible_user_id"), "?")] += 1
            till = t.get("complete_till", 0)
            if till and till < NOW:
                overdue.append(t)
            if t.get("entity_type") == "leads" and t.get("entity_id"):
                per_lead[t["entity_id"]].append((t.get("text") or "").strip().lower())

        print(f"\n  MUDDATI O'TGAN vazifalar: {len(overdue)} ta")
        for t in sorted(overdue, key=lambda x: x.get("complete_till", 0))[:20]:
            days_over = int((NOW - t.get("complete_till", NOW)) / DAY)
            print(f"    [{t.get('entity_id')}] {days_over} kun kechikkan: {(t.get('text') or '')[:70]}")

        print("\n  Mas'ul bo'yicha ochiq vazifalar:")
        for label, count in by_user.most_common():
            print(f"    {count:4d}  {label}")

        # Duplicate detection: same lead, ≥80% word overlap
        print("\n  DUBLIKAT vazifalar (bitta bitimda o'xshash matn):")
        dup_count = 0
        for lead_id, texts in per_lead.items():
            if len(texts) < 2:
                continue
            reported = set()
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    w1, w2 = set(texts[i].split()), set(texts[j].split())
                    if not w1 or not w2:
                        continue
                    overlap = len(w1 & w2) / max(len(w1), len(w2))
                    if overlap >= 0.8 and (lead_id, i) not in reported:
                        dup_count += 1
                        reported.add((lead_id, i))
                        print(f"    [{lead_id}] x{len(texts)}: {texts[i][:65]}")
                        break
        if not dup_count:
            print("    (topilmadi)")
        else:
            print(f"    JAMI dublikat juftliklar: {dup_count}")

        # Leads with no next action
        open_lead_ids = {
            l["id"] for l in leads if l.get("status_id") not in (142, 143)
        }
        leads_with_tasks = set(per_lead.keys())
        no_action = open_lead_ids - leads_with_tasks
        print(f"\n  KEYINGI QADAMSIZ ochiq bitimlar (birorta ochiq vazifa yo'q): {len(no_action)} ta")
        lead_names = {l["id"]: l.get("name", "")[:40] for l in leads}
        for lid in list(no_action)[:15]:
            print(f"    [{lid}] {lead_names.get(lid, '?')}")

    def run(self) -> None:
        print(f"\nAmoCRM LIVE AUDIT — {datetime.now().isoformat(timespec='seconds')}")
        print(f"(faqat o'qish — hech narsa o'zgartirilmaydi)\n")
        self.audit_account()
        user_map = self.audit_users()
        pipe_map = self.audit_pipelines()
        leads = self.audit_leads(pipe_map, user_map)
        self.audit_tasks(leads, user_map)
        print("\n" + "=" * 70)
        print("AUDIT YAKUNLANDI")
        print("=" * 70)


if __name__ == "__main__":
    AmoAuditor().run()
