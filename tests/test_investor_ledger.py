import pytest
from src.services.finance.investor_ledger import InvestorLedgerService

def test_investor_lifecycle():
    service = InvestorLedgerService()
    inv = service.register_investor("INV-01", "Akrom Aliyev", 100000000.0, 25.0)
    assert inv.available_capital == 100000000.0
    deal = service.allocate_deal("DEAL-501", "INV-01", "PRJ-SPIN-01", 40000000.0)
    assert deal.allocated_amount == 40000000.0
    closed = service.close_deal("DEAL-501", 80000000.0)
    assert closed.investor_profit == 20000000.0
    assert closed.total_payout_due == 60000000.0
