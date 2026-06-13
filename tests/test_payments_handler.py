from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.payments import successful_payment_callback


@pytest.mark.asyncio
async def test_successful_invoice_payment_enters_confirmed_finance_workflow():
    payment = SimpleNamespace(
        invoice_payload="invoice_pay_2001",
        telegram_payment_charge_id="charge-1",
        total_amount=1_500_000,
        currency="UZS",
    )
    update = SimpleNamespace(
        message=SimpleNamespace(
            successful_payment=payment,
            reply_text=AsyncMock(),
        ),
        effective_user=SimpleNamespace(id=777, first_name="Client"),
    )
    context = SimpleNamespace(
        bot_data={
            "finance_payment_context": {
                "invoice_pay_2001": {
                    "client_id": "client-777",
                    "seller_id": "seller-12",
                    "lead_id": 2001,
                    "deal_link": "https://example.amocrm.com/leads/detail/2001",
                    "airtable_project_id": "recProject1",
                    "celebration_chat_id": -100123,
                }
            }
        }
    )
    finance = MagicMock()
    finance.announce_income = AsyncMock(return_value={"workflow_id": "finance-1"})
    finance.confirm_income = AsyncMock()

    await successful_payment_callback(
        update,
        context,
        db=MagicMock(),
        invoicer=MagicMock(),
        finance_workflow=finance,
    )

    finance.announce_income.assert_awaited_once()
    finance.confirm_income.assert_awaited_once_with(
        "finance-1",
        confirmed_by="telegram_payment_gateway",
        confirmer_role="payment_gateway",
    )
