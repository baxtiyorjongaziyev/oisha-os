from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinancePolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False


class FinancePolicy:
    FINANCE_ROLES = frozenset(
        {"finance", "moliya", "accountant", "buxgalter", "owner", "payment_gateway"}
    )

    def validate_announcement(
        self,
        *,
        source_event_id: str,
        amount: float,
        currency: str,
        client_id: str,
        seller_id: str,
        lead_id: int,
        deal_link: str,
        airtable_project_id: str,
    ) -> None:
        required = {
            "source_event_id": source_event_id,
            "currency": currency,
            "client_id": client_id,
            "seller_id": seller_id,
            "lead_id": lead_id,
            "deal_link": deal_link,
            "airtable_project_id": airtable_project_id,
        }
        if float(amount or 0) <= 0:
            raise ValueError("amount_required")
        for name, value in required.items():
            if value in (None, "", 0):
                raise ValueError(f"{name}_required")

    def evaluate_confirmation(self, confirmer_role: str) -> FinancePolicyDecision:
        if str(confirmer_role or "").strip().casefold() not in self.FINANCE_ROLES:
            return FinancePolicyDecision(False, "finance_role_required")
        return FinancePolicyDecision(True, "finance_confirmation_allowed")

    def evaluate_adjustment(
        self,
        *,
        operation: str,
        amount: float,
        owner_approved: bool,
    ) -> FinancePolicyDecision:
        normalized = str(operation or "").strip().casefold()
        if normalized not in {"refund", "write_off", "writeoff"}:
            return FinancePolicyDecision(False, "unsupported_finance_adjustment")
        if float(amount or 0) <= 0:
            return FinancePolicyDecision(False, "amount_required")
        if not owner_approved:
            return FinancePolicyDecision(
                False,
                "owner_approval_required",
                requires_approval=True,
            )
        return FinancePolicyDecision(
            True,
            "owner_approved_adjustment",
            requires_approval=True,
        )

    def assert_final_file_handoff_allowed(
        self,
        *,
        contract_total: float,
        confirmed_paid: float,
    ) -> bool:
        if float(confirmed_paid or 0) < float(contract_total or 0):
            raise ValueError("outstanding_debt_blocks_file_handoff")
        return True
