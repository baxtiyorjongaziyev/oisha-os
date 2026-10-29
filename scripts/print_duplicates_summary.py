import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('data/active_duplicates_report.json', encoding='utf-8') as f:
    d = json.load(f)

print(f"Jami faol bitimlar soni: {d['total_active']}")
print(f"Dublikat telefon raqamlar soni: {d['phone_duplicates_count']}")
print(f"Ulardan kelib chiqqan ortiqcha bitimlar: {d['total_phone_dup_deals']}")

print("\n" + "="*80)
print("DUBLIKAT TELEFONLAR VA ULARNING FAOL BITIMLARI:")
print("="*80)
for p, lds in sorted(d['phone_duplicates'].items(), key=lambda x: -len(x[1])):
    print(f"\nTelefon: +{p} ({len(lds)} ta bitim):")
    for l in lds:
        print(f"   • Bitim #{l['id']} — '{l['name']}' | Voronka: {l['pipeline']} | Bosqich: {l['status']}")
