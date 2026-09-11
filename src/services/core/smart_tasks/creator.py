"""
SmartTaskCreator main engine class and factory helpers.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.context import app_ctx
from src.services.core.smart_tasks.analyzer import TaskAnalyzerMixin
from src.services.core.smart_tasks.context_builder import ContextBuilderMixin

logger = logging.getLogger("SmartTaskCreator")


class SmartTaskCreator(ContextBuilderMixin, TaskAnalyzerMixin):
    """
    AI yordamida lidlarni tahlil qilib, AmoCRM da to'g'ri tasklar ochuvchi tizim.
    """

    def __init__(self, token_file: str = "data/amocrm_token.json"):
        from src.settings import settings

        self.token_file = token_file
        subdomain = getattr(settings, "AMOCRM_SUBDOMAIN", "jonbranding")
        self.base_url = f"https://{subdomain}.amocrm.ru"
        self._token: Optional[str] = None
        self._token_expires: float = 0


# Singleton
app_ctx.creator: Optional[SmartTaskCreator] = None


def get_smart_task_creator() -> SmartTaskCreator:
    """SmartTaskCreator singleton."""
    if app_ctx.creator is None:
        app_ctx.creator = SmartTaskCreator()
    return app_ctx.creator


async def run_smart_task_creation(dry_run: bool = False) -> dict:
    """BackgroundMonitor dan chaqiriladi."""
    creator = get_smart_task_creator()
    return await creator.analyze_and_create_tasks(dry_run=dry_run)
