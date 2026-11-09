from datetime import datetime
import pytest
from src.services.customer_360.cooling_customers import (
    CoolingCustomerDetector,
    CustomerProfile,
    RetentionMission,
)

def test_cooling_customer_detection():
    detector = CoolingCustomerDetector(cooling_threshold_days=60, critical_churn_days=120)
    ref_date = datetime(2026, 11, 1)
    clients = [
        CustomerProfile(
            client_id="C-001",
            client_name="Artel Electronics",
            last_deal_date="2026-10-15",
            total_ltv=120000000.0,
            primary_service="Rebrending",
            manager="Farrux",
        ),
        CustomerProfile(
            client_id="C-002",
            client_name="Chust Pichoqlari",
            last_deal_date="2026-08-01",
            total_ltv=45000000.0,
            primary_service="Brending",
            manager="Madina",
        ),
    ]
    cooling = detector.detect_cooling(clients, as_of_date=ref_date)
    assert len(cooling) == 1
    assert cooling[0].risk_level == "yuqori"
    mission = detector.generate_mission(cooling[0])
    assert mission.client_name == "Chust Pichoqlari"
    assert len(mission.action_steps) == 3
