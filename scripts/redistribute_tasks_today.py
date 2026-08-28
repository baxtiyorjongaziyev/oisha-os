"""amoCRM: Bugungi va muddati o'tgan vazifalarni qayta taqsimlash.

- Bugunga 50ta vazifa qo'yadi (mavjudlardan)
- Muddati o'tganlarni ham bugunga ko'chiradi
- Jami bugun uchun 25tadan oshmaydigan qilib taqsimlaydi
"""
import datetime
import json
import os
import sys
import time
import requests

TASHKENT_TZ = datetime.timezone(datetime.timedelta(hours=5))


def get_tashkent_timestamp(year, month, day, hour=18, minute=0):
    """Return unix timestamp for specific Tashkent time (UTC+5)."""
    dt = datetime.datetime(year, month, day, hour, minute, tzinfo=TASHKENT_TZ)
    return int(dt.timestamp())


def today_tashkent():
    return datetime.datetime.now(TASHKENT_TZ).date()


def generate_schedule(start_date, total_items, per_day=25):
    """Generate distribution plan: per_day tasks per working day, skip Sundays."""
    schedule = []
    current_date = start_date
    remaining = total_items

    while remaining > 0:
        if current_date.weekday() == 6:  # Skip Sunday
            current_date += datetime.timedelta(days=1)
            continue

        count_today = min(remaining, per_day)
        target_ts = get_tashkent_timestamp(
            current_date.year, current_date.month, current_date.day, hour=18
        )
        schedule.append({
            "date_str": current_date.strftime("%Y-%m-%d (%A)"),
            "timestamp": target_ts,
            "count": count_today
        })
        remaining -= count_today
        current_date += datetime.timedelta(days=1)

    return schedule


def fetch_all_open_tasks(headers):
    """Fetch all open (not completed) tasks from amoCRM."""
    all_tasks = []
    page = 1
    while True:
        r = requests.get(
            f'https://jonbrandingagency.amocrm.ru/api/v4/tasks?limit=250&page={page}&filter[is_completed]=0',
            headers=headers
        )
        if r.status_code != 200:
            print(f"  API xato: {r.status_code} (page {page})")
            break
        data = r.json()
        t_list = data.get('_embedded', {}).get('tasks', [])
        all_tasks.extend(t_list)
        if not data.get('_links', {}).get('next') or len(t_list) < 250:
            break
        page += 1
        time.sleep(0.3)
    return all_tasks


def main():
    # Token
    token_path = os.path.join("data", "amocrm_token.json")
    if not os.path.exists(token_path):
        print(f"XATO: {token_path} topilmadi. Oracle VM da ishga tushiring.")
        sys.exit(1)

    token = json.load(open(token_path))['access_token']
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    today = today_tashkent()
    today_start_ts = get_tashkent_timestamp(today.year, today.month, today.day, hour=0, minute=0)
    today_end_ts = get_tashkent_timestamp(today.year, today.month, today.day, hour=23, minute=59)
    now_ts = int(time.time())

    print(f"Bugun: {today.strftime('%Y-%m-%d (%A)')}")
    print(f"Hozirgi vaqt (UTC): {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M')}")
    print()

    # 1. Barcha ochiq vazifalarni olish
    print("1. Barcha ochiq vazifalar yuklanmoqda...")
    all_tasks = fetch_all_open_tasks(headers)
    print(f"   Jami ochiq vazifalar: {len(all_tasks)}")

    # 2. Kategoriyalash
    overdue_tasks = []      # Muddati o'tganlar
    today_tasks = []        # Bugungilar  
    future_tasks = []       # Kelajakdagilar

    for t in all_tasks:
        deadline = t.get('complete_till', 0)
        if deadline < today_start_ts:
            overdue_tasks.append(t)
        elif deadline <= today_end_ts:
            today_tasks.append(t)
        else:
            future_tasks.append(t)

    print(f"   Muddati o'tganlar: {len(overdue_tasks)}")
    print(f"   Bugungilar: {len(today_tasks)}")
    print(f"   Kelajakdagilar: {len(future_tasks)}")
    print()

    # 3. Qayta taqsimlash rejasi:
    # - Muddati o'tganlar + bugungilar = barchasini birlashtirish
    # - Bugunga 25ta, qolganlarini keyingi kunlarga 25tadan
    tasks_to_redistribute = overdue_tasks + today_tasks
    total_to_redistribute = len(tasks_to_redistribute)

    if total_to_redistribute == 0:
        print("Qayta taqsimlash uchun vazifa yo'q!")
        return

    print(f"2. Qayta taqsimlanadigan vazifalar: {total_to_redistribute}")
    print(f"   (muddati o'tgan: {len(overdue_tasks)} + bugungi: {len(today_tasks)})")

    # Bugundan boshlab 25tadan taqsimlash
    schedule = generate_schedule(today, total_to_redistribute, per_day=25)

    print(f"\n--- Taqsimlash rejasi (25/kun, Yakshanbasiz) ---")
    for s in schedule:
        print(f"   {s['date_str']}: {s['count']} ta vazifa (Deadline: 18:00)")

    # 4. Vazifalarni yangilash
    tasks_to_update = []
    task_idx = 0
    for s in schedule:
        for _ in range(s['count']):
            t = tasks_to_redistribute[task_idx]
            tasks_to_update.append({
                "id": t["id"],
                "complete_till": s["timestamp"]
            })
            task_idx += 1

    print(f"\n3. {len(tasks_to_update)} ta vazifa yangilanmoqda (20talab)...")
    updated_count = 0
    chunk_size = 20

    for i in range(0, len(tasks_to_update), chunk_size):
        chunk = tasks_to_update[i:i + chunk_size]
        r = requests.patch(
            'https://jonbrandingagency.amocrm.ru/api/v4/tasks',
            headers=headers,
            json=chunk
        )
        if r.status_code in (200, 204):
            updated_count += len(chunk)
            print(f"   Batch {i // chunk_size + 1}: {len(chunk)} ta yangilandi (Jami: {updated_count})")
        else:
            print(f"   XATO batch {i // chunk_size + 1}: status {r.status_code}, {r.text[:200]}")
        time.sleep(0.4)

    print(f"\n✅ {updated_count} ta vazifa muvaffaqiyatli qayta taqsimlandi!")
    print(f"   Bugun ({today}): 25 ta")
    if len(schedule) > 1:
        print(f"   Keyingi kunlar: {', '.join(s['date_str'] + ': ' + str(s['count']) + ' ta' for s in schedule[1:])}")


if __name__ == "__main__":
    main()
