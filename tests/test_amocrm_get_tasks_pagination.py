import asyncio
from unittest.mock import MagicMock, patch

from src.services.core.crm.amocrm import tasks_notes


def _resp(n, start=0):
    r = MagicMock(status_code=200)
    r.json.return_value = {"_embedded": {"tasks": [{"id": start + i} for i in range(n)]}}
    return r


def test_get_tasks_fetches_all_pages():
    cls = next(v for v in vars(tasks_notes).values() if isinstance(v, type) and hasattr(v, "get_tasks"))
    obj = cls.__new__(cls)
    obj.access_token = "x"
    obj.base_url = "https://example.amocrm.ru"
    obj._get_headers = lambda: {}
    pages = [_resp(250, 0), _resp(250, 250), _resp(10, 500)]
    with patch.object(tasks_notes.requests, "get", side_effect=pages) as g:
        tasks = asyncio.run(obj.get_tasks(is_completed=False))
    assert len(tasks) == 510
    assert g.call_count == 3
    assert g.call_args_list[2].kwargs["params"]["page"] == 3
