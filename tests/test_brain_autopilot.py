import pytest
from pathlib import Path
from src.services.core.brain.cross_channel_sync import CrossChannelBrainSync, sanitize_text
from src.services.core.brain.finance_brain_synthesizer import FinanceBrainSynthesizer
from src.services.core.brain.weekly_review_synthesizer import WeeklyReviewSynthesizer


def test_sanitize_text():
    raw = "Parol: secret123, karta: 8600 1234 5678 9012, va telefon."
    clean = sanitize_text(raw)
    assert "secret123" not in clean
    assert "8600 1234 5678 9012" not in clean
    assert "[KARTA MA'LUMOTI]" in clean
    assert "[YASHIRILGAN]" in clean


def test_cross_channel_sync(tmp_path: Path):
    vault = tmp_path / "TestVault"
    (vault / "60-Wiki").mkdir(parents=True)
    
    syncer = CrossChannelBrainSync(vault_path=vault)
    success = syncer.sync_deal_and_call(
        lead_id=12345,
        lead_name="Test Brand",
        phone="+998901234567",
        price=5000000.0,
        status_name="Muzokara",
        transcript="Bizga yangi logotip va qadoqlash kerak.",
        ai_analysis="Mijoz byudjetga rozi, tezkorlik talab qilyapti.",
        telegram_messages=[{"sender": "Mijoz", "text": "Assalomu alaykum", "date": "2026-08-20 10:00"}],
    )
    assert success is True
    
    note_file = vault / "60-Wiki" / "pages" / "Test Brand.md"
    assert note_file.exists()
    content = note_file.read_text(encoding="utf-8")
    assert "Test Brand" in content
    assert "5,000,000" in content
    assert "Muzokara" in content
    assert "yangi logotip" in content


def test_finance_brain_synthesizer(tmp_path: Path):
    vault = tmp_path / "TestVault"
    (vault / "20-Areas").mkdir(parents=True)
    
    fin_synth = FinanceBrainSynthesizer(vault_path=vault)
    success = fin_synth.generate_monthly_report(
        month_label="August 2026",
        total_income=15000000.0,
        total_expense=6000000.0,
        categories_breakdown={"Dizaynerlar": 3000000.0, "Marketing": 2000000.0, "Ofis": 1000000.0},
        top_projects=[{"name": "Kamila Pardalari", "income": 8000000.0, "expense": 2000000.0}],
        notes="Rentabellik yuqori darajada.",
    )
    assert success is True
    
    moliya_file = vault / "20-Areas" / "Moliya.md"
    assert moliya_file.exists()
    content = moliya_file.read_text(encoding="utf-8")
    assert "August 2026" in content
    assert "15,000,000" in content
    assert "6,000,000" in content
    assert "Dizaynerlar" in content
    assert "Kamila Pardalari" in content


def test_weekly_review_synthesizer(tmp_path: Path):
    vault = tmp_path / "TestVault"
    (vault / "20-Areas").mkdir(parents=True)
    
    weekly_synth = WeeklyReviewSynthesizer(vault_path=vault)
    success = weekly_synth.generate_weekly_review(
        week_label="Hafta 34, 2026",
        completed_items=["Kamila Pardalari patent topshirildi", "Tez Dizayn 4 ta banner bitdi"],
        bottlenecks=["Lidlar bilan kechiktirilgan aloqa"],
        top_goals_next_week=["Yangi 3 ta shartnoma imzolash", "Hisobchi AI to'liq avtopilotga o'tishi"],
        revenue_summary="12 000 000 UZS",
    )
    assert success is True
    
    review_file = vault / "20-Areas" / "Haftalik Review.md"
    assert review_file.exists()
    content = review_file.read_text(encoding="utf-8")
    assert "Hafta 34, 2026" in content
    assert "Kamila Pardalari patent topshirildi" in content
    assert "Lidlar bilan kechiktirilgan aloqa" in content
    assert "Yangi 3 ta shartnoma imzolash" in content
