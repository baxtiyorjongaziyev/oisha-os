import pytest
from src.services.finance.project_margin import (
    ProjectMarginCalculator,
    ProjectCostInput,
    ProjectMarginResult,
)

def test_profitable_project_margin():
    calc = ProjectMarginCalculator(default_hourly_rate=150000.0, default_tax_rate=0.04)
    input_data = ProjectCostInput(
        project_id="PRJ-101",
        project_name="Eko Qurilish Brending",
        client_name="Eko Qurilish MChJ",
        contract_amount=60000000.0,
        direct_expenses=5000000.0,
        internal_hours=80.0,
    )
    result = calc.calculate(input_data)
    assert result.net_profit == 40600000.0
    assert result.health_status == "foydali"
