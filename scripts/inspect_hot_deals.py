import glob
import json

deals = []
for p in glob.glob("data/utc_analysis/deals/*.json"):
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
        strat = d.get("amocrm_strategy", {})
        deals.append({
            "card_no": d.get("card_no"),
            "name": d.get("client_name"),
            "phone": d.get("phone"),
            "utc_status": d.get("utc_status"),
            "priority": strat.get("priority", "Noma'lum"),
            "real_status": d.get("real_status", "Noma'lum"),
            "need": d.get("need_and_context", ""),
            "bant": d.get("bant_analysis", {}),
            "target_pipeline": strat.get("target_pipeline", "Sotuv Bo'limi"),
            "target_stage": strat.get("target_stage", "Qayta aloqa"),
            "opening_hook": strat.get("call_opening_hook", ""),
            "closing_pitch": strat.get("closing_pitch", ""),
            "summary_uz": d.get("summary_uz", ""),
            "total_duration_sec": d.get("total_duration_sec", 0),
            "file": p
        })

print(f"Total analyzed deals so far: {len(deals)}")

# Scoring function to prioritize deals close to sale (Sotuvga yaqin)
def score_deal(deal):
    p = str(deal["priority"]).lower()
    st = str(deal["real_status"]).lower()
    score = 0
    if "p1" in p or "yuqori" in p or "urgent" in p:
        score += 100
    elif "p2" in p or "o'rta" in p:
        score += 50
    if "issiq" in st or "potensial_issiq" in st:
        score += 50
    elif "qayta_aloqa" in st:
        score += 25
    # Long call indicates deep conversation
    score += min(deal["total_duration_sec"] // 60, 40)
    return score

deals.sort(key=score_deal, reverse=True)

hot_deals = [d for d in deals if score_deal(d) >= 100]
p2_deals = [d for d in deals if 60 <= score_deal(d) < 100]

print(f"=== P1 HOT / SOTUVGA ENG YAQIN: {len(hot_deals)} ta ===")
for i, d in enumerate(hot_deals, 1):
    print(f"{i}. #{d['card_no']} | {d['name']} | {d['phone']} | Priority: {d['priority']} | Status: {d['real_status']} | Stage: {d['target_stage']} | Dur: {d['total_duration_sec']}s ({d['total_duration_sec']//60}m)")

print(f"\n=== P2 MEDIUM / QAYTA ALOQA: {len(p2_deals)} ta ===")
for i, d in enumerate(p2_deals[:10], 1):
    print(f"{i}. #{d['card_no']} | {d['name']} | {d['phone']} | Priority: {d['priority']} | Status: {d['real_status']} | Stage: {d['target_stage']} | Dur: {d['total_duration_sec']}s ({d['total_duration_sec']//60}m)")
