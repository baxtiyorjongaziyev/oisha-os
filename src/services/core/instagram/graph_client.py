"""
Meta Instagram Graph API Client.
Provides read-only access to profile, media, and account insights.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
import requests
import structlog

from src.settings import settings

logger = structlog.get_logger("InstagramGraphClient")


class InstagramGraphClient:
    """Read-only Meta Graph client for the connected Instagram professional account."""

    PROFILE_FIELDS = (
        "id,username,name,biography,website,followers_count,"
        "follows_count,media_count,profile_picture_url"
    )
    MEDIA_FIELDS = (
        "id,caption,media_type,media_product_type,permalink,"
        "thumbnail_url,timestamp,username,like_count,comments_count"
    )

    def __init__(self, settings_obj=None):
        self.settings = settings_obj or settings
        self.instagram_account_id = (
            getattr(self.settings, "META_INSTAGRAM_USER_ID", None)
            or getattr(self.settings, "META_INSTAGRAM_ACCOUNT_ID", None)
            or ""
        )
        self.page_id = getattr(self.settings, "META_PAGE_ID", None) or ""
        self.api_version = (
            os.environ.get("META_GRAPH_API_VERSION", "").strip() or "v19.0"
        )

    @property
    def access_token(self) -> str:
        token = getattr(self.settings, "META_PAGE_ACCESS_TOKEN", None)
        if token is None:
            return ""
        getter = getattr(token, "get_secret_value", None)
        return getter() if callable(getter) else str(token)

    @property
    def configured(self) -> bool:
        return bool(self.instagram_account_id and self.access_token)

    def _get_json(
        self, path: str, *, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call one read endpoint without logging or returning the access token."""
        if not self.configured:
            return {
                "ok": False,
                "error": "instagram_not_configured",
                "missing": [
                    name
                    for name, present in (
                        ("META_INSTAGRAM_USER_ID", bool(self.instagram_account_id)),
                        ("META_PAGE_ACCESS_TOKEN", bool(self.access_token)),
                    )
                    if not present
                ],
            }

        request_params = dict(params or {})
        request_params["access_token"] = self.access_token
        url = f"https://graph.facebook.com/{self.api_version}/{path.lstrip('/')}"
        try:
            response = requests.get(url, params=request_params, timeout=15)
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning(
                "[META] Read request failed",
                endpoint=path,
                error=type(exc).__name__,
            )
            return {"ok": False, "error": "meta_graph_unreachable"}
        except ValueError:
            return {
                "ok": False,
                "error": "invalid_meta_response",
                "status_code": response.status_code,
            }

        if response.status_code >= 400 or payload.get("error"):
            error = payload.get("error") or {}
            return {
                "ok": False,
                "error": error.get("message") or "meta_graph_error",
                "error_type": error.get("type"),
                "error_code": error.get("code"),
                "status_code": response.status_code,
            }

        payload["ok"] = True
        return payload

    def get_profile(self) -> Dict[str, Any]:
        """Return the connected Creator/Business account profile."""
        return self._get_json(
            self.instagram_account_id,
            params={"fields": self.PROFILE_FIELDS},
        )

    def list_media(self, limit: int = 10) -> Dict[str, Any]:
        """Return recent media for the connected account, newest first."""
        safe_limit = max(1, min(int(limit), 25))
        return self._get_json(
            f"{self.instagram_account_id}/media",
            params={"fields": self.MEDIA_FIELDS, "limit": safe_limit},
        )

    def get_account_insights(self) -> Dict[str, Any]:
        """Return a small read-only account insight set for diagnostics."""
        return self._get_json(
            f"{self.instagram_account_id}/insights",
            params={
                "metric": "reach,profile_views,website_clicks",
                "period": "day",
            },
        )
