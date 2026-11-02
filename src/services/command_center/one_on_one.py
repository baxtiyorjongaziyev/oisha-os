"""One-on-One (1:1) Meeting Coaching Dossier and Printable Agenda Service.

Prepares structured coaching dossiers for ROP/CEO and sales representatives
with achievements (wins), data-backed concerns, commitments, and reflective questions.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ManagerLevel:
    """Sales manager proficiency level (1 to 5)."""

    level: int
    title: str
    index: int
    target_conv: float
    target_score: int


@dataclass
class OneOnOneDossier:
    """Complete 1:1 meeting dossier ready for interactive review or print/PDF."""

    manager_id: str
    manager_name: str
    level: ManagerLevel
    as_of_label: str
    month_key: str
    wins: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    focus_skill: str = ""
    commitments: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    kpis: Dict[str, Any] = field(default_factory=dict)


class OneOnOneCoachService:
    """Generates structured 1:1 coaching agendas and evaluation dossiers."""

    def classify_level(self, conv_rate: float, ai_score: float) -> ManagerLevel:
        """Classify manager level from 1 (Boshlangʻich) to 5 (Master)."""
        idx = int((conv_rate * 3.0) + (ai_score * 0.5))
        idx = max(10, min(99, idx))

        if conv_rate >= 15.0 and ai_score >= 65:
            return ManagerLevel(level=5, title="Top Master", index=idx, target_conv=18.0, target_score=75)
        elif conv_rate >= 10.0 and ai_score >= 60:
            return ManagerLevel(level=4, title="Kuchli", index=idx, target_conv=15.0, target_score=68)
        elif conv_rate >= 5.0 and ai_score >= 50:
            return ManagerLevel(level=3, title="Barqaror", index=idx, target_conv=10.0, target_score=60)
        elif conv_rate >= 2.0 or ai_score >= 45:
            return ManagerLevel(level=2, title="Oʻsishda", index=idx, target_conv=5.0, target_score=55)
        else:
            return ManagerLevel(level=1, title="Boshlangʻich", index=idx, target_conv=3.0, target_score=50)

    def build_dossier(
        self,
        manager_data: Dict[str, Any],
        as_of_label: str = "31-iyul",
        month_key: str = "2026-07",
    ) -> OneOnOneDossier:
        """Build full 1:1 coaching dossier with wins, concerns, commitments, questions."""
        name = str(manager_data.get("name", "Menejer"))
        conv = float(manager_data.get("conv", 0.0))
        score = float(manager_data.get("score", 50.0))
        plan_pct = int(manager_data.get("plan_percent", 0))
        hot_sum = int(manager_data.get("hot_deals_sum", 0))
        hot_cnt = int(manager_data.get("hot_deals_count", 0))
        overdue_calls = int(manager_data.get("overdue_calls", 0))
        overdue_tasks = int(manager_data.get("overdue_tasks", 0))
        focus_skill = str(manager_data.get("focus_skill", "Yakunlash va keyingi qadam"))

        level = self.classify_level(conv, score)

        # 1. Wins (shundan boshlang)
        wins: List[str] = []
        if plan_pct >= 100:
            wins.append(f"Oy rejasi bajarildi: {plan_pct}%")
        elif plan_pct >= 70:
            wins.append(f"Rejaga yaqinlashmoqda: {plan_pct}%")
        if conv >= 10.0:
            wins.append(f"Konversiya jamoa yetakchilari qatorida: {conv}%")
        elif conv > 0:
            wins.append(f"Barqaror konversiya: {conv}%")
        if not wins:
            wins.append("Bu oy hali sezilarli yutuq yoʻq — kichik ijobiy oʻzgarishni toping")

        # 2. Concerns (raqam bilan)
        concerns: List[str] = []
        if hot_sum > 0:
            concerns.append(f"{hot_cnt} ta issiq bitim yopilishni kutmoqda ({hot_sum // 1_000_000} mln soʻm)")
        if overdue_calls > 0:
            concerns.append(f"{overdue_calls} ta vaʼda qilingan qayta qoʻngʻiroq kechikkan")
        if overdue_tasks > 0:
            concerns.append(f"{overdue_tasks} ta bitimda vazifa muddati oʻtgan")
        if not concerns:
            concerns.append("Hozircha tizimda jiddiy kechikishlar aniqlanmadi")

        # 3. Commitments (kelishuvlar)
        skill_commitment = f"'{focus_skill}' boʻyicha Darslik testidan 80%+ olish".replace("'", "«", 1).replace("'", "»", 1)
        commitments = [
            f"Bu hafta kamida {max(3, int(hot_cnt * 0.3))} ta sotuv yopish",
            "Kechikkan vazifalarni juma kunigacha 0 ga tushirish",
            f"«{focus_skill}» boʻyicha Darslik testidan 80%+ olish",
        ]

        # 4. Coaching questions (menejerning oʻzi javob topsin)
        questions = [
            "Vazifalar nega kechikmoqda — lid koʻpmi yoki vaqt rejasi yoʻqmi?",
            f"Oxirgi qoʻngʻiroqlardan birini birga eshitamiz: «{focus_skill}» qismini qanday qilgan boʻlardingiz?",
            "Rejaga yetish uchun mendan qanday yordam kerak?",
        ]

        kpis = {
            "fact": manager_data.get("fact", 0),
            "plan": manager_data.get("plan", 0),
            "percent": plan_pct,
            "conv": conv,
            "score": score,
        }

        return OneOnOneDossier(
            manager_id=str(manager_data.get("id", "mgr")),
            manager_name=name,
            level=level,
            as_of_label=as_of_label,
            month_key=month_key,
            wins=wins,
            concerns=concerns,
            focus_skill=focus_skill,
            commitments=commitments,
            questions=questions,
            kpis=kpis,
        )

    def to_printable_html(self, dossier: OneOnOneDossier) -> str:
        """Render standalone printable HTML agenda for one-on-one meeting."""
        wins_li = "".join(f"<li>{w}</li>" for w in dossier.wins)
        concerns_li = "".join(f"<li>{c}</li>" for c in dossier.concerns)
        commitments_li = "".join(f"<li>{cm}</li>" for cm in dossier.commitments)
        questions_li = "".join(f"<li>{q}</li>" for q in dossier.questions)

        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<title>1:1 Uchrashuv — {dossier.manager_name}</title>"
            "<style>body{font-family:sans-serif;padding:30px;color:#1e293b;}"
            ".head{border-bottom:2px solid #e2e8f0;padding-bottom:15px;margin-bottom:20px;}"
            ".sec{margin-bottom:18px;}h3{color:#0f172a;margin-bottom:6px;}ul{margin:0;padding-left:20px;}"
            "@media print{.btn{display:none;}}</style></head><body>"
            "<button class='btn' onclick='window.print()'>Chop etish / PDF</button>"
            f"<div class='head'><h2>1:1 Uchrashuv — {dossier.manager_name}</h2>"
            f"<p>{dossier.as_of_label} holatiga · Daraja {dossier.level.level}/5 ({dossier.level.title})</p></div>"
            f"<div class='sec'><h3>1. Yutuqlar (shundan boshlang)</h3><ul>{wins_li}</ul></div>"
            f"<div class='sec'><h3>2. Muammolar (raqam bilan)</h3><ul>{concerns_li}</ul></div>"
            f"<div class='sec'><h3>3. Kelishuvlar (keyingi hafta)</h3><ul>{commitments_li}</ul></div>"
            f"<div class='sec'><h3>4. Savollar (Coaching)</h3><ul>{questions_li}</ul></div>"
            "</body></html>"
        )
