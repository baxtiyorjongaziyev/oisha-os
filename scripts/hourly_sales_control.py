"""Oisha server hourly KPI report. Missing CRM evidence stays unknown."""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from html import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.daily_sales_calls_report import (
    TASHKENT, _api_url, send_telegram, split_message,
)
from src.services.call_analytics.moizvonki_roster import (
    load_excludes, load_roster, unmapped_accounts,
)
import requests


def fetch(start, end):
    rows, seen, offset = [], set(), 0
    for _ in range(200):
        response = requests.post(_api_url(os.environ.get('MOIZVONKI_DOMAIN')),
            json={'user_name': os.environ['MOIZVONKI_EMAIL'],
                  'api_key': os.environ['MOIZVONKI_API_KEY'], 'action': 'calls.list',
                  'from_date': start, 'to_date': end, 'max_results': 100,
                  'from_offset': offset, 'supervised': 1}, timeout=45)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get('results'), list) or data.get('error'):
            raise ValueError('Moizvonki response incomplete')
        for call in data['results']:
            key = str(call.get('id') or call.get('call_id') or (call.get('user_account'), call.get('start_time'), call.get('client_number'), call.get('direction')))
            if key not in seen:
                seen.add(key)
                if start <= int(call.get('start_time') or 0) < end:
                    rows.append(call)
        if not data.get('results_remains'):
            return rows
        nxt = int(data.get('results_next_offset') or 0)
        if nxt <= offset or not data['results']:
            raise ValueError('Moizvonki pagination incomplete')
        offset = nxt
    raise ValueError('Moizvonki page limit reached')


def render(calls, names, end, unmapped=None):
    grouped = {}
    for account, name in names.items():
        grouped.setdefault(name, set()).add(account.lower())
    parts = [f'<b>Sotuv nazorati · {end:%d.%m.%Y %H:%M}</b>',
             'Kunlik reja: 50 ta ≥3 daqiqalik suhbat · 3 uchrashuv · 1 sotuv.']
    for name, accounts in grouped.items():
        day = [c for c in calls if str(c.get('user_account', '')).lower() in accounts]
        hour = [c for c in day if int(c.get('start_time') or 0) >= int((end-timedelta(hours=1)).timestamp())]
        answered = [c for c in day if str(c.get('answered')) == '1']
        solid = sum(int(c.get('duration') or 0) >= 180 for c in answered)
        spoken = [c for c in hour if str(c.get('answered')) == '1']
        parts += [f'\n<b>{escape(name)}</b>',
                  f'Soatda: {len(hour)} urinish · {len(spoken)} javobli suhbat · {sum(int(c.get("duration") or 0) for c in spoken)/60:.1f} daqiqa.',
                  f'Kun boshidan: {len(day)} urinish · {len(answered)} javobli · {sum(int(c.get("duration") or 0) for c in answered)/60:.1f} daqiqa.',
                  f'≥3 daqiqa: {solid}/50 · qoldi: {max(0,50-solid)}.',
                  'Uchrashuv: tekshirilmagan / 3. Sotuv: tekshirilmagan / 1.']
        for c in spoken:
            who = c.get('client_name') or c.get('client_number') or 'Mijoz nomi noma’lum'
            parts.append(f'• {escape(str(who))} — {int(c.get("duration") or 0)/60:.1f} daq.')
        parts.append('Suhbat mazmuni va savdo konversiyasi: CRM/transkripsiya bilan bog‘lanmagan.')
    if unmapped:
        parts.append('\n<b>Ro‘yxatda yo‘q akkauntlar</b> (hisobotga kirmadi, config/moizvonki_roster.json ga qo‘shing):')
        for account, count in sorted(unmapped.items(), key=lambda item: (-item[1], item[0])):
            parts.append(f'• {escape(account)} — {count} qo‘ng‘iroq')
    parts += ['\nManba: Moizvonki, to‘liq sahifalangan davr. Suhbat davomiyligi sifat yoki sotuv isboti emas.',
              'Tavsiya: har suhbat oxirida keyingi qadam va vaqtni kelishing; bu umumiy tavsiya.']
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    end = datetime.now(TASHKENT).replace(minute=0, second=0, microsecond=0)
    start = end.replace(hour=9)
    names = load_roster()
    if not names:
        raise ValueError('Roster unavailable: config/moizvonki_roster.json')
    calls = fetch(int(start.timestamp()), int(end.timestamp()))
    exclude = [os.environ.get('MOIZVONKI_EMAIL', ''), *load_excludes()]
    text = render(calls, names, end, unmapped_accounts(calls, names, exclude))
    if args.dry_run:
        print(text)
        return
    for part in split_message(text):
        send_telegram(os.environ['BOT_TOKEN'], '-1003854308552', part, '115')
    print('Hourly report sent')


if __name__ == '__main__':
    main()
