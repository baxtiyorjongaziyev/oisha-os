"""AmoCRM task cleanup — finds and closes stale/duplicate tasks.

Modes:
  dry-run (default): prints what would be closed, no changes
  live:              closes tasks in AmoCRM after confirmation token check

Safety: requires CONFIRM_TEXT = "TOZALASH_TASDIQLANDI" when live=True.

Stale criteria  — bot-created tasks (prefix "Telegram suhbatidan:")
                  that are overdue by > STALE_DAYS days
Duplicate criteria — same lead, ≥ OVERLAP tasks with ≥ 80% word-overlap,
                    keep the newest, close the rest
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.settings import settings  # noqa: E402
from src.services.core.amocrm_sync import AmoCRMSync  # noqa: E402

import requests  # noqa: E402

CONFIRM_TEXT = "TOZALASH_TASDIQLANDI"
STALE_DAYS = 7          # close bot tasks overdue > N days
OVERLAP_THRESHOLD = 0.8  # word-overlap ratio for duplicates
MAX_PAGES = 20
NOW = int(time.time())
DAY = 86400


class AmoCRMTaskCleaner:
    def __init__(self, live: bool = False, confirm: str = "") -> None:
        self.live = live
        if live and confirm != CONFIRM_TEXT:
            raise ValueError(
                f"Live mode requires confirm='{CONFIRM_TEXT}'. "
                "Pass --live only when you are certain."
            )
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
        self.closed = 0
        self.skipped = 0
        self.errors = 0

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return self.amo._get_headers()

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.amo.base_url}{path}"
        r = requests.get(url, headers=self._headers(), params=params or {}, timeout=30)
        if r.status_code == 401 and self.amo.refresh_token():
            r = requests.get(url, headers=self._headers(), params=params or {}, timeout=30)
        if r.status_code in (204, 404):
            return {}
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, body: list) -> bool:
        if not self.live:
            return True
        url = f"{self.amo.base_url}{path}"
        r = requests.patch(url, headers=self._headers(), json=body, timeout=30)
        if r.status_code == 401 and self.amo.refresh_token():
            r = requests.patch(url, headers=self._headers(), json=body, timeout=30)
        return r.status_code in (200, 204)

    def _get_all_tasks(self, extra_params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        page = 1
        while page <= MAX_PAGES:
            params = {"page": page, "limit": 250, "filter[is_completed]": 0}
            if extra_params:
                params.update(extra_params)
            data = self._get("/api/v4/tasks", params)
            chunk = data.get("_embedded", {}).get("tasks", [])
            if not chunk:
                break
            items.extend(chunk)
            if len(chunk) < 250:
                break
            page += 1
        return items

    # ── Closing helper ───────────────────────────────────────────────────────

    def _close_task(self, task_id: int, reason: str) -> None:
        tag = "[DRY-RUN]" if not self.live else "[LIVE]"
        ok = self._patch(f"/api/v4/tasks/{task_id}", [{"id": task_id, "is_completed": True}])
        if ok:
            self.closed += 1
            print(f"  {tag} ✓ Closed task {task_id} — {reason}")
        else:
            self.errors += 1
            print(f"  {tag} ✗ Failed to close task {task_id}")

    # ── Stale bot tasks ──────────────────────────────────────────────────────

    def find_stale_bot_tasks(self, tasks: list[dict]) -> list[dict]:
        stale = []
        for t in tasks:
            text = (t.get("text") or "").strip()
            if not text.lower().startswith("telegram suhbatidan:"):
                continue
            complete_till = t.get("complete_till", 0) or 0
            if complete_till == 0:
                continue
            days_overdue = (NOW - complete_till) / DAY
            if days_overdue > STALE_DAYS:
                stale.append(t)
        return stale

    def close_stale_bot_tasks(self, tasks: list[dict]) -> None:
        stale = self.find_stale_bot_tasks(tasks)
        print(f"\n{'='*70}")
        print(f"ESKIRGAN BOT VAZIFALARI (>{STALE_DAYS} kun kechikkan, prefix 'Telegram suhbatidan:')")
        print(f"{'='*70}")
        print(f"  Topildi: {len(stale)} ta")
        for t in stale:
            days_over = int((NOW - (t.get("complete_till") or NOW)) / DAY)
            text_preview = (t.get("text") or "")[:60]
            lead_id = t.get("entity_id")
            print(f"  [{t['id']}] lead={lead_id}  {days_over}kun kechikkan: {text_preview}")
            self._close_task(t["id"], f"stale bot task ({days_over}d overdue)")

    # ── Duplicate tasks ──────────────────────────────────────────────────────

    def find_duplicate_groups(self, tasks: list[dict]) -> list[list[dict]]:
        per_lead: dict[int, list[dict]] = defaultdict(list)
        for t in tasks:
            if t.get("entity_type") == "leads" and t.get("entity_id"):
                per_lead[t["entity_id"]].append(t)

        dup_groups: list[list[dict]] = []
        for lead_id, lead_tasks in per_lead.items():
            if len(lead_tasks) < 2:
                continue
            used = set()
            for i, t1 in enumerate(lead_tasks):
                if i in used:
                    continue
                group = [t1]
                w1 = set((t1.get("text") or "").lower().split())
                for j, t2 in enumerate(lead_tasks):
                    if j <= i or j in used:
                        continue
                    w2 = set((t2.get("text") or "").lower().split())
                    if not w1 or not w2:
                        continue
                    overlap = len(w1 & w2) / max(len(w1), len(w2))
                    if overlap >= OVERLAP_THRESHOLD:
                        group.append(t2)
                        used.add(j)
                if len(group) > 1:
                    used.add(i)
                    dup_groups.append(group)
        return dup_groups

    def close_duplicate_tasks(self, tasks: list[dict]) -> None:
        groups = self.find_duplicate_groups(tasks)
        print(f"\n{'='*70}")
        print(f"DUBLIKAT VAZIFALAR ({int(OVERLAP_THRESHOLD*100)}%+ so'z mos kelish)")
        print(f"{'='*70}")
        if not groups:
            print("  (dublikat topilmadi)")
            return
        print(f"  Dublikat guruhlar: {len(groups)} ta")
        for group in groups:
            lead_id = group[0].get("entity_id")
            # Sort by id descending — keep newest (highest id), close the rest
            sorted_group = sorted(group, key=lambda t: t["id"], reverse=True)
            keep = sorted_group[0]
            close_list = sorted_group[1:]
            print(f"\n  Lead {lead_id}: {len(group)} o'xshash vazifa — SAQLASH [{keep['id']}]")
            print(f"    Saqlanadi: {(keep.get('text') or '')[:70]}")
            for t in close_list:
                print(f"    O'chiriladi [{t['id']}]: {(t.get('text') or '')[:70]}")
                self._close_task(t["id"], "duplicate task")

    # ── Main ─────────────────────────────────────────────────────────────────

    def run(self) -> dict:
        mode_label = "LIVE" if self.live else "DRY-RUN"
        print(f"\nAmoCRM TASK CLEANUP — {datetime.now().isoformat(timespec='seconds')} [{mode_label}]")
        if not self.live:
            print("(Faqat ko'rsatish — hech narsa o'zgartirilmaydi. --live uchun CONFIRM_TEXT kerak)")

        print("\nBarcha ochiq vazifalar yuklanmoqda...")
        all_tasks = self._get_all_tasks()
        print(f"  Jami ochiq vazifalar: {len(all_tasks)}")

        self.close_stale_bot_tasks(all_tasks)
        self.close_duplicate_tasks(all_tasks)

        print(f"\n{'='*70}")
        print(f"YAKUNLANDI [{mode_label}]")
        print(f"  Yopildi/belgilandi: {self.closed}")
        print(f"  Xatolar: {self.errors}")
        print(f"{'='*70}")

        return {
            "success": self.errors == 0,
            "live": self.live,
            "closed": self.closed,
            "errors": self.errors,
            "total_tasks_scanned": len(all_tasks),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AmoCRM task cleanup")
    parser.add_argument("--live", action="store_true", help="Actually close tasks")
    args = parser.parse_args()

    confirm = CONFIRM_TEXT if args.live else ""
    result = AmoCRMTaskCleaner(live=args.live, confirm=confirm).run()
    sys.exit(0 if result["success"] else 1)
