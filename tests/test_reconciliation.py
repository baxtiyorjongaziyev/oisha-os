import pytest
from src.services.reporter.reconciliation import (
    ReconciliationService,
    ReconciliationEntry,
    ReconciliationStatement,
)

def test_reconciliation_zero_entries():
    service = ReconciliationService()
    statement = service.generate_statement(
        client_name="Test Holding MChJ",
        period_start="2026-01-01",
        period_end="2026-01-31",
        initial_balance=0.0,
        entries=[],
    )
    assert statement.client_name == "Test Holding MChJ"
    assert statement.total_debit == 0.0
    assert statement.total_credit == 0.0
    assert statement.closing_balance == 0.0
    assert statement.status == "yopilgan"

def test_reconciliation_calculation_with_debt():
    service = ReconciliationService()
    raw_entries = [
        {
            "date": "2026-02-05",
            "document_number": "INV-101",
            "document_type": "hisob-faktura",
            "description": "Brending strategiyasi bosqichi",
            "debit": 50000000.0,
            "credit": 0.0,
        },
        {
            "date": "2026-02-10",
            "document_number": "PAY-882",
            "document_type": "toʻlov",
            "description": "50% avans toʻlovi",
            "debit": 0.0,
            "credit": 25000000.0,
        },
    ]
    statement = service.generate_statement(
        client_name="Grand Savdo MChJ",
        period_start="2026-02-01",
        period_end="2026-02-28",
        initial_balance=10000000.0,
        entries=raw_entries,
    )
    assert statement.closing_balance == 35000000.0
    assert statement.status == "qarzdor"
    assert "Grand Savdo MChJ" in statement.to_text()
