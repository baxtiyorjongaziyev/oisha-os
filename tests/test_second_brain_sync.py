import pytest
from pathlib import Path
from src.services.core import second_brain_sync

@pytest.mark.asyncio
async def test_save_voice_note(tmp_path, monkeypatch):
    monkeypatch.setattr(second_brain_sync, 'resolve_vault_path', lambda: tmp_path)
    
    res = await second_brain_sync.save_voice_note(
        text='Yangi brending loyihasi boyicha uchrashuv otkazish kerak',
        sender_name='Baxtiyorjon',
    )
    assert res is not None
    saved_file = Path(res)
    assert saved_file.exists()
    assert '00-Inbox' in str(saved_file)
    
    content = saved_file.read_text(encoding='utf-8')
    assert 'Yangi brending loyihasi' in content
    assert 'Baxtiyorjon' in content

@pytest.mark.asyncio
async def test_save_won_case(tmp_path, monkeypatch):
    monkeypatch.setattr(second_brain_sync, 'resolve_vault_path', lambda: tmp_path)
    
    case_data = {
        'title': 'AIVA Brending Konseptsiyasi',
        'client': 'AIVA Group',
        'short_description': 'Suniy intellekt brendi uchun toliq vizual identifikatsiya yaratildi.',
        'challenge': 'Bozorda kuchli va innovatsion brend yaratish talabi.',
        'solution': 'Futuristik logotip va brandbook ishlab chiqildi.',
        'results': 'Savdolar 3 barobarga oshdi va bozorga muvaffaqiyatli kirdi.',
        'tags': ['branding', 'ai', 'portfolio'],
    }
    lead_data = {
        'id': 123456,
        'price': 15000000,
        'name': 'AIVA Group',
    }
    
    res = await second_brain_sync.save_won_case(case_data, lead_data)
    assert res is not None
    saved_file = Path(res)
    assert saved_file.exists()
    assert '10-Projects' in str(saved_file)
    
    content = saved_file.read_text(encoding='utf-8')
    assert 'AIVA Brending Konseptsiyasi' in content
    assert 'Futuristik logotip' in content
    assert '15,000,000' in content
