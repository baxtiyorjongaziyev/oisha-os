"""Oisha server hourly KPI report. Missing CRM evidence stays unknown."""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from html import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.daily_sales_calls_report import (
    TASHKENT, _api_url, parse_rep_names, send_telegram, split_message,
)
import requests


def fetch(start, end, accounts=None):
    rows, seen = [], set()
    user_list = list(accounts) if accounts else [os.environ.get('MOIZVONKI_EMAIL', '')]
    for user_name in user_list:
        if not user_name:
            continue
        offset = 0
        for _ in range(50):
            response = requests.post(_api_url(os.environ.get('MOIZVONKI_DOMAIN')),
                json={'user_name': user_name,
                      'api_key': os.environ['MOIZVONKI_API_KEY'], 'action': 'calls.list',
                      'from_date': start, 'to_date': end, 'max_results': 100,
                      'from_offset': offset, 'supervised': 1}, timeout=30)
            if response.status_code == 403:
                break
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get('results'), list) or data.get('error'):
                break
            for call in data['results']:
                if not call.get('user_account'):
                    call['user_account'] = user_name
                key = str(call.get('id') or call.get('call_id') or (call.get('user_account'), call.get('start_time'), call.get('client_number'), call.get('direction')))
                if key not in seen:
                    seen.add(key)
                    if start <= int(call.get('start_time') or 0) < end:
                        rows.append(call)
            if not data.get('results_remains'):
                break
            nxt = int(data.get('results_next_offset') or 0)
            if nxt <= offset or not data['results']:
                break
            offset = nxt
    return rows


def render(calls, names, end):
    grouped = {}
    for account, name in names.items():
        grouped.setdefault(name, set()).add(account.lower())
    parts = [
        f'🌸 <b>Oisha | Sotuv nazorati · {end:%d.%m.%Y %H:%M}</b>',
        '🎯 <b>Kunlik maqsad:</b> 50 ta sifatli suhbat (≥3 daq) · 3 uchrashuv · 1 yopilgan savdo',
        '━━━━━━━━━━━━━━━━━━━━',
    ]
    for name, accounts in grouped.items():
        day = [c for c in calls if str(c.get('user_account', '')).lower() in accounts]
        hour = [c for c in day if int(c.get('start_time') or 0) >= int((end-timedelta(hours=1)).timestamp())]
        answered = [c for c in day if str(c.get('answered')) == '1']
        solid = sum(int(c.get('duration') or 0) >= 180 for c in answered)
        spoken = [c for c in hour if str(c.get('answered')) == '1']
        qoldi = max(0, 50 - solid)

        if solid >= 25:
            cheer = '🔥 <i>Ajoyib temp, yarmidan oshdi!</i>'
        elif solid > 0:
            cheer = f'⚡️ <i>Qani, davom etamiz — yana {qoldi} ta qoldi!</i>'
        else:
            cheer = '⏳ <i>Hali suhbat boshlanmadi, tezroq faollashamiz!</i>'

        parts += [
            f'\n🧑‍💼 <b>{escape(name)}</b> — {cheer}',
            f'• Oxirgi soatda: {len(hour)} urinish · {len(spoken)} javobli suhbat ({sum(int(c.get("duration") or 0) for c in spoken)/60:.1f} daq)',
            f'• Kun boshidan: {len(day)} urinish · {len(answered)} javobli ({sum(int(c.get("duration") or 0) for c in answered)/60:.1f} daq)',
            f'• 🎯 Sifatli suhbatlar (≥3 daqiqa): <b>{solid}/50</b> (qoldi: {qoldi})',
        ]
        if spoken:
            parts.append('  <i>Soatdagi suhbatlar:</i>')
            for c in spoken[:4]:
                who = c.get('client_name') or c.get('client_number') or 'Mijoz'
                parts.append(f'  • {escape(str(who))} — {int(c.get("duration") or 0)/60:.1f} daq')

    parts += [
        '\n━━━━━━━━━━━━━━━━━━━━',
        '💡 <b>Oishadan maslahat:</b> Har bir qo\'ng\'iroqni muqobil tanlov (Alternative Closing) bilan aniq uchrashuvga yoki to\'lov sanasiga bog\'lang!',
    ]
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    now = datetime.now(TASHKENT)
    end = now.replace(second=0, microsecond=0)
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if start > end:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    names = parse_rep_names(os.environ.get('MOIZVONKI_REP_NAMES', ''))
    if not names:
        raise ValueError('Roster unavailable')
    text = render(fetch(int(start.timestamp()), int(end.timestamp()), accounts=set(names.keys())), names, end)
    if args.dry_run:
        print('Read-only report built; roster size:', len(set(names.values())))
        print(text)
        return
    for part in split_message(text):
        send_telegram(os.environ['BOT_TOKEN'], '-1003854308552', part, '115')
    print('Hourly report sent')


if __name__ == '__main__':
    main()
