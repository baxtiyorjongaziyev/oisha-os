import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.instagram.leadgen_sheets import get_leadgen_spreadsheet

sh = get_leadgen_spreadsheet()
for ws in sh.worksheets():
    print(f"\nWorksheet: {ws.title} (id={ws.id}, total_grid_rows={ws.row_count})")
    records = ws.get_all_values()
    print(f"  Rows with data: {len(records)}")
    if len(records) > 0:
        print(f"  Headers: {records[0]}")
    if len(records) > 1:
        print(f"  Last 5 rows:")
        for r in records[-5:]:
            print(f"    {r[:6]}")
