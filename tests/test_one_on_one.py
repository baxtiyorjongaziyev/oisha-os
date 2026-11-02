"""Unit tests for One-on-One Coaching Dossier Service."""
import pytest
from src.services.command_center.one_on_one import OneOnOneCoachService, OneOnOneDossier


def test_classify_level():
    service = OneOnOneCoachService()
    master = service.classify_level(conv_rate=22.0, ai_score=78.0)
    assert master.level == 5
    assert master.title == "Top Master"

    novice = service.classify_level(conv_rate=1.5, ai_score=35.0)
    assert novice.level == 1
    assert novice.title == "Boshlangʻich"


def test_build_dossier():
    service = OneOnOneCoachService()
    mgr_data = {
        "id": "mgr_51",
        "name": "Kamola Karimova",
        "fact": 369_740_000,
        "plan": 150_000_000,
        "plan_percent": 246,
        "conv": 16.8,
        "score": 65.0,
        "focus_skill": "Yakunlash va keyingi qadam",
        "hot_deals_sum": 588_900_000,
        "overdue_calls": 120,
        "overdue_tasks": 25,
    }
    dossier = service.build_dossier(mgr_data)
    assert isinstance(dossier, OneOnOneDossier)
    assert dossier.manager_name == "Kamola Karimova"
    assert len(dossier.wins) >= 2
    assert len(dossier.concerns) >= 2
    assert len(dossier.commitments) >= 2
    assert len(dossier.questions) >= 3


def test_to_printable_html():
    service = OneOnOneCoachService()
    mgr_data = {
        "id": "mgr_52",
        "name": "Mohira Karimova",
        "fact": 200_000_000,
        "plan": 200_000_000,
        "conv": 12.0,
        "score": 60.0,
    }
    dossier = service.build_dossier(mgr_data)
    html = service.to_printable_html(dossier)
    assert "<!DOCTYPE html>" in html
    assert "Mohira Karimova" in html
    assert "window.print()" in html
