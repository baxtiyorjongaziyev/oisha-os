"""Evidence candidates for the owner funnel; never autonomous KPI credits."""
MEANINGFUL = {
    "need": "Mijoz o‘z ehtiyoji yoki biznes muammosini tasdiqlagan",
    "fit": "Ehtiyojga mos xizmat muhokama qilingan",
    "next_step": "Mijoz bilan aniq keyingi qadam kelishilgan (faqat uchrashuv emas)",
}
EVQN = {
    "need": "Ehtiyoj aniqlashtirilgan",
    "timing": "Qachonga kerakligi aniqlashtirilgan",
    "decision_process": "O‘zi qaror qiladimi; bo‘lmasa kim va qanday jalb qilinishi aniqlashtirilgan",
    "price": "Narx yoki narxlash doirasi va mijozning munosabati muhokama qilingan; budjetni taxmin qilmang",
}


def _criteria(raw, keys, transcript):
    raw = raw if isinstance(raw, dict) else {}
    result = []
    for key, label in keys.items():
        item = raw.get(key)
        item = item if isinstance(item, dict) else {}
        quote, reason = item.get("quote"), item.get("reason")
        valid = (isinstance(quote, str) and 3 <= len(quote) <= 1000 and quote in transcript
                 and isinstance(reason, str) and bool(reason.strip()))
        status = item.get("status")
        status = status if valid and status in ("met", "unmet") else "unknown"
        result.append({"id": key, "label": label, "status": status,
                       "quote": quote if valid else "", "reason": reason[:1000] if valid else ""})
    return result


def evaluate_funnel(raw, transcript, sales_type):
    groups = {}
    for name, keys in (("meaningful", MEANINGFUL), ("evqn", EVQN)):
        items = _criteria(raw.get(name + "_criteria"), keys, transcript)
        statuses = {item["status"] for item in items}
        status = ("excluded" if not sales_type else "not_met" if "unmet" in statuses
                  else "evidence_candidate" if statuses == {"met"} else "unknown")
        groups[name] = {"status": status, "criteria": items}
    return {"version": "jonbranding-funnel-evidence-v1", **groups,
            "human_review_required": True, "kpi_credited": False,
            "duration_verified": False, "meeting_held_verified": False, "sale_verified": False}


def funnel_prompt():
    sections = "; ".join(f"{name}_criteria: " + ", ".join(f"{k}={v}" for k, v in keys.items())
                         for name, keys in (("meaningful", MEANINGFUL), ("evqn", EVQN)))
    return (
        "\nVORONKA DALILLARI (qo‘shimcha JSON): " + sections + ". "
        'Har band {"status":"met|unmet|unknown","quote":"aynan iqtibos","reason":"izoh"}. '
        "Mijoz aytmagan ehtiyoj yoki rozilikni menejer monologidan yasamang. "
        "Dalil yo‘q bo‘lsa unknown; sukutni rad etish yoki rozilik deb baholamang. "
        "Narx aytilgani to‘lov yoki sotuv emas; taklif uchrashuv o‘tkazilgani emas. "
        "Qaror qiluvchi boshqa odam bo‘lishi avtomatik unmet emas. "
        "3 daqiqa va mijozlar sonini transkriptdan taxmin qilmang.\n"
    )
