import os, sys

# Ensure project root is on PYTHONPATH for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.services.core.instagram.leadgen_sheets import get_leadgen_spreadsheet

sh = get_leadgen_spreadsheet()
if sh is None:
    print('[ERROR] Spreadsheet not found – likely missing service account credentials.')
    sys.exit(1)

for ws in sh.worksheets():
    print(f"\nWorksheet: {ws.title} (id={ws.id}, rows={ws.row_count})")
    records = ws.get_all_values()
    print(f"  Rows with data: {len(records)}")
    if records:
        # Replace problematic № symbol with '#'
        safe_header = [h.replace('\u2116', '#') if isinstance(h, str) else h for h in records[0]]
        print(f"  Headers: {safe_header}")
    if len(records) > 1:
        print('  Last 5 rows (first 6 columns):')
        for r in records[-5:]:
            print(f"    {r[:6]}")
