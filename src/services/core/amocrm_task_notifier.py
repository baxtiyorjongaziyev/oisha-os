"""
Facade for AmoCRM Task Notifier (@jonairobot).
Delegates to modular implementations in src.services.core.crm.task_notifier.
"""
from src.services.core.crm.task_notifier.formatter import (
    DEFAULT_FORWARD_GROUP_ID,
    DEFAULT_FORWARD_TOPIC_ID,
    DEFAULT_SUBDOMAIN,
    PIPELINE_MAP,
    STATUS_MAP,
    TASK_TYPE_MAP,
    _extract_custom_field_value,
    _format_price,
    _format_timestamp,
    format_task_notification,
)
from src.services.core.crm.task_notifier.notifier import (
    AmoCrmTaskNotifier,
    parse_amocrm_task_webhook_data,
)

__all__ = [
    "AmoCrmTaskNotifier",
    "parse_amocrm_task_webhook_data",
    "_format_timestamp",
    "_format_price",
    "_extract_custom_field_value",
    "format_task_notification",
    "DEFAULT_FORWARD_GROUP_ID",
    "DEFAULT_FORWARD_TOPIC_ID",
    "DEFAULT_SUBDOMAIN",
    "PIPELINE_MAP",
    "STATUS_MAP",
    "TASK_TYPE_MAP",
]
