import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.agents.contracts.templates import load_contract_templates
from src.services.core.crm.auditor.classifier import ClassifierMixin
from src.services.core.service_config.modules import get_default_modules


@pytest.mark.parametrize('factory', [get_default_modules, load_contract_templates])
def test_catalog_snapshot_and_fresh_instances(factory):
    first = factory()
    serialized = json.dumps([asdict(value) for value in first.values()],
                            ensure_ascii=False, sort_keys=True, default=str)
    expected = json.loads(Path(__file__).with_name('batch1_catalog_hashes.json').read_text())
    assert hashlib.sha256(serialized.encode()).hexdigest() == expected[factory.__name__]
    second = factory()
    assert list(first) == list(second)
    for key in first:
        assert first[key] == second[key]
        assert first[key] is not second[key]
    item = next(iter(first.values()))
    mutable = item.deliverables if hasattr(item, 'deliverables') else item.clauses
    mutable.clear()
    assert factory() == second


def make_auditor(category='Mijoz', duplicate=False):
    auditor = ClassifierMixin()
    for name, result in {
        'is_lead_audited': False, 'get_contact_phone_and_username': ('phone', 'user'),
        'get_or_lookup_telegram_user': (77, 'resolved'),
        'get_telegram_history_and_unanswered': ('private', True, '2h'),
        'find_shared_group_chats': [('group', 'Title')],
        'get_group_chat_history_and_unanswered': ('group history', True, '3h'),
        'get_lead_tasks': [{'text': 'existing'}],
        'get_call_notes_and_transcripts': ('unused', 'calls'),
        'get_lead_notes_history': 'notes',
        'classify_contact': (category, 'reason', 'summary', ' task ', ' draft '),
        'save_audit_result': None,
    }.items():
        setattr(auditor, name, AsyncMock(return_value=result))
    auditor.serialize_tasks = Mock(return_value='tasks')
    auditor.serialize_lead_details = Mock(return_value='details')
    auditor.score_lead_temperature = Mock(return_value=('Iliq', 'warm'))
    auditor.is_duplicate_task = Mock(return_value=duplicate)
    auditor.amocrm = SimpleNamespace(add_lead_note=Mock(), create_task=AsyncMock(),
                                    add_lead_tag=AsyncMock())
    auditor.tg_client = SimpleNamespace(edit_draft=AsyncMock())
    return auditor


@pytest.mark.asyncio
@pytest.mark.parametrize('category,duplicate', [('Mijoz', False), ('Boshqa', True)])
async def test_audit_outputs_and_side_effects(category, duplicate):
    auditor = make_auditor(category, duplicate)
    lead = {'id': '12', 'name': 'Lead', 'contacts': [{'id': 3, 'name': 'Contact'}],
            'responsible_user_id': 9}
    assert await auditor.audit_lead_by_data(lead) == category
    context = auditor.classify_contact.await_args.kwargs
    assert context['username'] == 'resolved'
    assert context['group_history'] == '--- Guruh: Title ---\ngroup history'
    assert context['tasks_history'] == 'tasks'
    assert '(2h)' in context['telegram_unanswered_info']
    assert '(3h)' in context['telegram_unanswered_info']
    saved = auditor.save_audit_result.await_args.kwargs
    assert saved['telegram_history'] == 'private\n\n--- Guruh: Title ---\ngroup history'
    assert saved['temperature'] == ('Iliq' if category == 'Mijoz' else None)
    assert saved['task_text'] == ' task '
    auditor.tg_client.edit_draft.assert_awaited_once_with(77, 'draft')
    assert auditor.amocrm.add_lead_note.call_count == (3 if duplicate else 2)
    if duplicate:
        auditor.amocrm.create_task.assert_not_awaited()
    else:
        task = auditor.amocrm.create_task.await_args.kwargs
        assert task['element_id'] == 12
        assert task['responsible_user_id'] == 9
        assert task['text'] == '🤖 Oisha-OS Keyingi Qadam:\ntask'
    assert auditor.amocrm.add_lead_tag.await_args_list[0].args == (12, category)


@pytest.mark.asyncio
async def test_audit_guards_force_and_recoverable_failures():
    auditor = make_auditor()
    assert await auditor.audit_lead_by_data({}) is None
    auditor.is_lead_audited.return_value = True
    assert await auditor.audit_lead_by_data({'id': 12}) == 'skipped'
    auditor.classify_contact.assert_not_awaited()
    auditor.find_shared_group_chats.side_effect = RuntimeError('groups')
    auditor.amocrm.add_lead_note.side_effect = RuntimeError('note')
    auditor.tg_client.edit_draft.side_effect = RuntimeError('draft')
    auditor.amocrm.create_task.side_effect = RuntimeError('task')
    auditor.amocrm.add_lead_tag.side_effect = RuntimeError('tag')
    assert await auditor.audit_lead_by_data({'id': 12}, force=True) == 'Mijoz'
    context = auditor.classify_contact.await_args.kwargs
    assert context['contact_name'] == "Noma'lum Kontakt"
    assert context['telegram_unanswered_info'] == 'Barcha Telegram xabarlariga javob berilgan.'
    auditor.save_audit_result.assert_awaited_once()
