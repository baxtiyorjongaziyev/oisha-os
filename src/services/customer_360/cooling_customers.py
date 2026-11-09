from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class CustomerProfile:
    client_id: str
    client_name: str
    last_deal_date: str
    total_ltv: float = 0.0
    primary_service: str = "Brending"
    manager: str = "Boshqaruvchi"
    last_contact_date: Optional[str] = None


@dataclass
class CoolingCustomer:
    profile: CustomerProfile
    days_silent: int
    risk_level: str


@dataclass
class RetentionMission:
    client_id: str
    client_name: str
    manager: str
    risk_level: str
    recommended_upsell: str
    action_steps: List[str]
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )


class CoolingCustomerDetector:
    UPSELL_MAP: Dict[str, str] = {
        "Brending": "Qadoq dizayni va brendbook amaliyoti auditi",
        "Rebrending": "Ijtimoiy tarmoqlar vizual uslubi (SMM retainer)",
        "Qadoq dizayni": "Yangi mahsulot liniyasi uchun qadoq adaptatsiyasi",
        "Sayt": "Texnik qoʻllab-quvvatlash va konversiya auditi",
    }

    def __init__(
        self, cooling_threshold_days: int = 60, critical_churn_days: int = 120
    ):
        self.cooling_threshold = cooling_threshold_days
        self.critical_churn = critical_churn_days

    def detect_cooling(
        self,
        profiles: List[CustomerProfile],
        as_of_date: Optional[datetime] = None,
    ) -> List[CoolingCustomer]:
        current_dt = as_of_date or datetime.now()
        results: List[CoolingCustomer] = []

        for p in profiles:
            try:
                deal_dt = datetime.strptime(p.last_deal_date, "%Y-%m-%d")
                delta_days = (current_dt - deal_dt).days
            except ValueError:
                continue

            if delta_days >= self.cooling_threshold:
                risk = self._calculate_risk(delta_days)
                results.append(
                    CoolingCustomer(
                        profile=p, days_silent=delta_days, risk_level=risk
                    )
                )

        results.sort(key=lambda x: x.days_silent, reverse=True)
        return results

    def _calculate_risk(self, days: int) -> str:
        if days >= self.critical_churn:
            return "kritik"
        if days >= 90:
            return "yuqori"
        return "oʻrta"

    def generate_mission(self, cooling: CoolingCustomer) -> RetentionMission:
        p = cooling.profile
        upsell = self.UPSELL_MAP.get(
            p.primary_service,
            "Brend auditi va keyingi chorak marketing strategiyasi",
        )

        steps = [
            f"1. {p.client_name} rahbariga samimiy munosabat qoʻngʻirogʻi qiling yoki Telegram orqali hol-ahvol soʻrang.",
            f"2. Oldingi {p.primary_service} natijalarini eslatib, bepul mini-audit taqdim eting.",
            f"3. Yangi {upsell} boʻyicha qisqa 15 daqiqalik strategik sessiya taklif qiling.",
        ]

        return RetentionMission(
            client_id=p.client_id,
            client_name=p.client_name,
            manager=p.manager,
            risk_level=cooling.risk_level,
            recommended_upsell=upsell,
            action_steps=steps,
        )
