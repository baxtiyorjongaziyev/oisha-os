from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReconciliationEntry:
    date: str
    document_number: str
    document_type: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0


@dataclass
class ReconciliationStatement:
    client_name: str
    period_start: str
    period_end: str
    initial_balance: float
    total_debit: float
    total_credit: float
    closing_balance: float
    status: str
    entries: List[ReconciliationEntry] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    def to_text(self) -> str:
        lines = [
            "=" * 70,
            "SOLISHTIRMA DALOLATNOMA (AKT SVERKA)",
            f"Mijoz / Kontragent: {self.client_name}",
            f"Davr: {self.period_start} dan {self.period_end} gacha",
            f"Tuzilgan vaqti: {self.created_at}",
            "=" * 70,
            f"Boshlangʻich qoldiq: {self.initial_balance:,.2f} soʻm",
            "-" * 70,
            f"{'Sana':<12} | {'Hujjat #':<10} | {'Turi':<14} | {'Debit (ish)':<12} | {'Kredit (pul)':<12} | {'Qoldiq':<12}",
            "-" * 70,
        ]

        for item in self.entries:
            lines.append(
                f"{item.date:<12} | {item.document_number:<10} | {item.document_type:<14} | "
                f"{item.debit:>12,.2f} | {item.credit:>12,.2f} | {item.balance:>12,.2f}"
            )

        lines.extend(
            [
                "-" * 70,
                f"Jami koʻrsatilgan xizmatlar (Debit): {self.total_debit:,.2f} soʻm",
                f"Jami qabul qilingan toʻlovlar (Kredit): {self.total_credit:,.2f} soʻm",
                f"Yakuniy qoldiq: {self.closing_balance:,.2f} soʻm ({self.status.upper()})",
                "=" * 70,
                "Jon Branding rahbari: _________________ (Imzo)",
                f"{self.client_name} rahbari: _________________ (Imzo)",
                "=" * 70,
            ]
        )
        return "\n".join(lines)


class ReconciliationService:
    def generate_statement(
        self,
        client_name: str,
        period_start: str,
        period_end: str,
        initial_balance: float = 0.0,
        entries: Optional[List[Dict[str, Any]]] = None,
    ) -> ReconciliationStatement:
        raw_items = entries or []
        calculated: List[ReconciliationEntry] = []
        running = float(initial_balance)
        tot_deb = 0.0
        tot_crd = 0.0

        for raw in raw_items:
            deb = float(raw.get("debit", 0.0))
            crd = float(raw.get("credit", 0.0))
            tot_deb += deb
            tot_crd += crd
            running += deb - crd
            calculated.append(
                ReconciliationEntry(
                    date=str(raw.get("date", "")),
                    document_number=str(raw.get("document_number", "")),
                    document_type=str(raw.get("document_type", "hujjat")),
                    description=str(raw.get("description", "")),
                    debit=deb,
                    credit=crd,
                    balance=round(running, 2),
                )
            )

        status = "qarzdor" if running > 0 else ("haqdor" if running < 0 else "yopilgan")
        return ReconciliationStatement(
            client_name=client_name,
            period_start=period_start,
            period_end=period_end,
            initial_balance=round(float(initial_balance), 2),
            total_debit=round(tot_deb, 2),
            total_credit=round(tot_crd, 2),
            closing_balance=round(running, 2),
            status=status,
            entries=calculated,
        )
