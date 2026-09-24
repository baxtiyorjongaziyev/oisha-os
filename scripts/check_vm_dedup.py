import json, os

fn = 'data/processed_leadgen_ids.json'
if os.path.exists(fn):
    with open(fn) as f:
        data = json.load(f)
    print("Total processed in JSON:", len(data))
    for lid in ['2984202781960154', '2067828480770247', '1624925035886608', '947631508415345', '1864423427858837', '1436772051692238', '1794217338368981', '957932850050833']:
        print(f"  Lead {lid}: {'ALREADY IN JSON' if lid in data else 'MISSING FROM JSON'}")
else:
    print("File not found:", fn)
