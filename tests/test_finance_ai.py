import pytest
from fastapi import HTTPException

from src.api.routes.finance_ai import AgentRequest, analyze_finance, router
from src.services.core.finance.agents import create_agent


def test_cashflow_agent_uses_only_supplied_transactions():
    result = create_agent("cashflow").process(
        {
            "currency": "uzs",
            "transactions": [
                {"type": "income", "amount": "125.50"},
                {"type": "expense", "amount": "25.25"},
            ],
        }
    )
    assert result == {
        "currency": "UZS",
        "income": "125.50",
        "expense": "25.25",
        "net": "100.25",
        "status": "positive",
        "transaction_count": 2,
    }


@pytest.mark.parametrize("amount", ["NaN", "Infinity", -1])
def test_cashflow_rejects_non_finite_or_negative_amount(amount):
    with pytest.raises(ValueError, match="amount"):
        create_agent("cashflow").process(
            {"transactions": [{"type": "income", "amount": amount}]}
        )


@pytest.mark.asyncio
async def test_unknown_agent_is_a_bounded_client_error():
    with pytest.raises(HTTPException) as error:
        await analyze_finance(AgentRequest(agent="fin_gpt", payload={}))
    assert error.value.status_code == 400


def test_route_is_read_only_and_explicitly_mounted_on_router():
    route = next(item for item in router.routes if item.path == "/api/finance/ai/analyze")
    assert route.methods == {"POST"}
    permissions = [
        dependency.dependency.__oisha_permissions__
        for dependency in route.dependencies
    ]
    assert permissions == [("finance:read",)]
