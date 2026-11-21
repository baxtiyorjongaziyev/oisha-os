"""Complete, authenticated task reads; a failed page is never an empty list."""
import requests


async def read_tasks(client, is_completed=False):
    if not client.access_token:
        client._load_token()
    tasks = {}
    for page in range(1, 1001):
        response = await client._request_with_auth(
            requests.get, f"{client.base_url}/api/v4/tasks",
            params={"filter[is_completed]": int(is_completed), "limit": 250, "page": page},
            timeout=30,
        )
        if response.status_code == 204:
            client.last_error = None
            return list(tasks.values())
        if response.status_code != 200:
            client.last_error = f"get_tasks_http_{response.status_code}"
            raise RuntimeError(client.last_error)
        payload = response.json()
        batch = payload.get("_embedded", {}).get("tasks")
        if not isinstance(batch, list):
            raise RuntimeError("get_tasks_invalid_payload")
        before = len(tasks)
        for task in batch:
            tasks[task["id"]] = task
        if not payload.get("_links", {}).get("next"):
            client.last_error = None
            return list(tasks.values())
        if len(tasks) == before:
            raise RuntimeError("get_tasks_pagination_stalled")
    raise RuntimeError("get_tasks_pagination_limit")
