"""Complete-or-error amoCRM collection reads for reporting."""
import asyncio

import requests


class CRMCollectionUnavailable(RuntimeError):
    """The collection is unknown; no partial records may be aggregated."""


async def _request_page(crm, url, params):
    async def request():
        if hasattr(crm, "_request_with_auth"):
            return await crm._request_with_auth(
                requests.get, url, params=params, timeout=30,
            )
        return await asyncio.to_thread(
            requests.get, url, headers=crm._get_headers(), params=params, timeout=30,
        )

    response = await request()
    if response.status_code == 401 and hasattr(crm, "refresh_token"):
        if await asyncio.to_thread(crm.refresh_token):
            response = await request()
    return response


async def fetch_collection(crm, collection, extra_params=None, *,
                           embedded_key=None, page_size=250, max_pages=100):
    """Return all records, including a verified empty result, or raise."""
    if crm is None:
        raise CRMCollectionUnavailable("amoCRM is not configured")
    try:
        if hasattr(crm, "_load_token") and not getattr(crm, "access_token", None):
            crm._load_token()
        key = embedded_key or collection
        url = f"{crm.base_url}/api/v4/{collection}"
        items = []
        for page in range(1, max_pages + 1):
            params = {**(extra_params or {}), "limit": page_size, "page": page}
            response = await _request_page(crm, url, params)
            if response.status_code == 204:
                return items
            if response.status_code != 200:
                raise CRMCollectionUnavailable(
                    f"{collection} page {page}: HTTP {response.status_code}"
                )
            payload = response.json()
            batch = payload["_embedded"][key]
            if not isinstance(batch, list) or any(not isinstance(row, dict) for row in batch):
                raise CRMCollectionUnavailable(f"{collection}: invalid collection")
            items.extend(batch)
            has_next = bool(payload.get("_links", {}).get("next"))
            if not has_next and len(batch) < page_size:
                return items
        raise CRMCollectionUnavailable(f"{collection}: pagination limit reached")
    except CRMCollectionUnavailable:
        raise
    except Exception as exc:
        # Do not expose response bodies, URLs with credentials or request errors.
        raise CRMCollectionUnavailable(f"{collection}: fetch failed") from exc
