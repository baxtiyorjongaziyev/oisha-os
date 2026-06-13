from scripts.amocrm_task_cleanup import AmoCRMTaskCleaner


def _cleaner_with_statuses(statuses: dict[int, int | None]) -> AmoCRMTaskCleaner:
    cleaner = AmoCRMTaskCleaner.__new__(AmoCRMTaskCleaner)
    cleaner._get_lead_status = lambda lead_id: statuses.get(lead_id)
    return cleaner


def test_selects_open_oisha_task_on_closed_lead():
    cleaner = _cleaner_with_statuses({10: 143})
    tasks = [
        {
            "id": 1,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": False,
            "text": "🤖 Oisha-OS Keyingi Qadam:\nMijoz bilan bog'laning",
        }
    ]

    assert cleaner.find_oisha_tasks_on_closed_leads(tasks) == tasks


def test_does_not_select_human_task_on_closed_lead():
    cleaner = _cleaner_with_statuses({10: 143})
    tasks = [
        {
            "id": 2,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": False,
            "text": "Mijoz bilan bog'laning",
        }
    ]

    assert cleaner.find_oisha_tasks_on_closed_leads(tasks) == []


def test_does_not_select_oisha_task_on_active_lead():
    cleaner = _cleaner_with_statuses({10: 12345})
    tasks = [
        {
            "id": 3,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": False,
            "text": "Oisha-OS Keyingi Qadam: qo'ng'iroq qiling",
        }
    ]

    assert cleaner.find_oisha_tasks_on_closed_leads(tasks) == []


def test_does_not_select_completed_task_or_unknown_lead_status():
    cleaner = _cleaner_with_statuses({10: 143, 11: None})
    tasks = [
        {
            "id": 4,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": True,
            "text": "Oisha-OS Keyingi Qadam: qo'ng'iroq qiling",
        },
        {
            "id": 5,
            "entity_type": "leads",
            "entity_id": 11,
            "is_completed": False,
            "text": "Oisha-OS Keyingi Qadam: qo'ng'iroq qiling",
        },
    ]

    assert cleaner.find_oisha_tasks_on_closed_leads(tasks) == []


def test_closes_only_selected_oisha_tasks_on_closed_leads():
    cleaner = _cleaner_with_statuses({10: 142, 11: 12345})
    cleaner.closed = 0
    cleaner.errors = 0
    closed_ids: list[int] = []
    cleaner._close_task = lambda task_id, reason: closed_ids.append(task_id)
    tasks = [
        {
            "id": 6,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": False,
            "text": "🤖 Oisha-OS Keyingi Qadam: tekshiring",
        },
        {
            "id": 7,
            "entity_type": "leads",
            "entity_id": 10,
            "is_completed": False,
            "text": "Menejer qo'ygan vazifa",
        },
        {
            "id": 8,
            "entity_type": "leads",
            "entity_id": 11,
            "is_completed": False,
            "text": "🤖 Oisha-OS Keyingi Qadam: tekshiring",
        },
    ]

    cleaner.close_oisha_tasks_on_closed_leads(tasks)

    assert closed_ids == [6]


def test_lead_status_lookup_fails_closed_on_unexpected_error():
    cleaner = AmoCRMTaskCleaner.__new__(AmoCRMTaskCleaner)
    cleaner._get = lambda path: (_ for _ in ()).throw(RuntimeError("temporary API error"))

    assert cleaner._get_lead_status(10) is None
