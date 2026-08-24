import datetime
import json
import time
import requests

def get_tashkent_timestamp(year, month, day, hour=18, minute=0):
    """Return unix timestamp for specific Tashkent time (UTC+5)."""
    tz = datetime.timezone(datetime.timedelta(hours=5))
    dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
    return int(dt.timestamp())

def generate_schedule_dates(start_date, total_items, per_day=50):
    """Generate list of target timestamps for working days (skipping Sundays)."""
    schedule = []
    current_date = start_date
    remaining = total_items
    
    while remaining > 0:
        if current_date.weekday() == 6:  # Skip Sunday
            current_date += datetime.timedelta(days=1)
            continue
            
        count_today = min(remaining, per_day)
        target_ts = get_tashkent_timestamp(
            current_date.year, current_date.month, current_date.day, hour=18, minute=0
        )
        schedule.append({
            "date_str": current_date.strftime("%Y-%m-%d (%A)"),
            "timestamp": target_ts,
            "count": count_today
        })
        remaining -= count_today
        current_date += datetime.timedelta(days=1)
        
    return schedule

def main():
    token = json.load(open('data/amocrm_token.json'))['access_token']
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    print("1. Fetching all open tasks from amoCRM...")
    all_tasks = []
    page = 1
    while True:
        r = requests.get(
            f'https://jonbrandingagency.amocrm.ru/api/v4/tasks?limit=250&page={page}&filter[is_completed]=0',
            headers=headers
        )
        if r.status_code != 200:
            break
        data = r.json()
        t_list = data.get('_embedded', {}).get('tasks', [])
        all_tasks.extend(t_list)
        if not data.get('_links', {}).get('next') or len(t_list) < 250:
            break
        page += 1
        time.sleep(0.3)

    now_ts = int(time.time())
    overdue_tasks = [t for t in all_tasks if t.get('complete_till', 0) < now_ts]
    print(f"Total Open: {len(all_tasks)}, Overdue to reschedule: {len(overdue_tasks)}")

    if not overdue_tasks:
        print("No overdue tasks found!")
        return

    # Start from today
    start_date = datetime.date(2026, 8, 24)
    schedule = generate_schedule_dates(start_date, len(overdue_tasks), per_day=50)

    print("\n--- Distribution Plan (50 per day, skipping Sundays) ---")
    for s in schedule:
        print(f"   * {s['date_str']}: {s['count']} tasks (Deadline: 18:00)")

    # Prepare batches
    tasks_to_update = []
    task_idx = 0
    for s in schedule:
        for _ in range(s['count']):
            t = overdue_tasks[task_idx]
            tasks_to_update.append({
                "id": t["id"],
                "complete_till": s["timestamp"]
            })
            task_idx += 1

    print(f"\n2. Updating {len(tasks_to_update)} tasks in batches of 20...")
    updated_count = 0
    chunk_size = 20

    for i in range(0, len(tasks_to_update), chunk_size):
        chunk = tasks_to_update[i:i+chunk_size]
        r = requests.patch(
            'https://jonbrandingagency.amocrm.ru/api/v4/tasks',
            headers=headers,
            json=chunk
        )
        if r.status_code in (200, 204):
            updated_count += len(chunk)
            print(f"   Updated chunk {i//chunk_size + 1}/{(len(tasks_to_update)+chunk_size-1)//chunk_size}: {len(chunk)} tasks (Total: {updated_count})")
        else:
            print(f"   Failed chunk {i//chunk_size + 1}: status {r.status_code}, {r.text[:100]}")
        time.sleep(0.4)

    print(f"\n[OK] All {updated_count} overdue tasks successfully rescheduled into 50/day batches!")

if __name__ == "__main__":
    main()
