import pytest
from src.services.core.instagram.leadgen_delivery import try_claim_leadgen
from src.services.core.instagram.leadgen_formatter import build_telegram_message


def test_try_claim_leadgen_atomic():
    import uuid
    test_id = f"test_atomic_claim_{uuid.uuid4().hex}"
    assert try_claim_leadgen(test_id, pid=100) is True
    # Second claim must fail
    assert try_claim_leadgen(test_id, pid=200) is False


def test_build_telegram_message_dynamic_pipeline():
    msg = build_telegram_message(
        "leadgen_111",
        52367729,
        "Jonibek",
        "+998889310025",
        "",
        {"brend_nomi": "Mishka"},
        pipeline_name="Sotuv Bo'limi",
    )
    assert "🎯 <b>Voronka:</b> Sotuv Bo&#x27;limi" in msg or "🎯 <b>Voronka:</b> Sotuv Bo'limi" in msg
    assert "Target LEADs" not in msg

    msg_utc = build_telegram_message(
        "leadgen_222",
        52367730,
        "Ali",
        "+998901234567",
        "",
        {},
        pipeline_name="UTC",
    )
    assert "🎯 <b>Voronka:</b> UTC" in msg_utc
    assert "Target LEADs" not in msg_utc
