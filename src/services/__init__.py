"""Compatibility layer for legacy ``src.services.*`` imports.

The codebase was partially refactored into ``src.services.core``,
``src.services.debug`` and ``src.services.utils``. A lot of runtime code
still imports the old flat module paths, so we register lightweight alias
modules here to keep the canonical runtime working while the refactor is
completed.
"""

from importlib import import_module
import sys
import types

_ALIASES = {
    "access_manager": "src.services.utils.access_manager",
    "action_parser": "src.services.core.action_parser",
    "activity_monitor": "src.services.core.activity_monitor",
    "admin_bot": "src.services.core.admin_bot",
    "advisor_agent": "src.services.core.advisor_agent",
    "airtable_sync": "src.services.core.airtable_sync",
    "amocrm_sync": "src.services.core.amocrm_sync",
    "audit_agent": "src.services.core.audit_agent",
    "auto_lead_agent": "src.services.core.auto_lead_agent",
    "chat_bridge": "src.services.core.chat_bridge",
    "checklist_manager": "src.services.core.checklist_manager",
    "crm_audit": "src.services.debug.crm_audit",
    "crm_integration": "src.services.core.crm_integration",
    "crm_night_shift": "src.services.core.crm_night_shift",
    "crm_service": "src.services.core.crm_service",
    "enterprise_reporter": "src.services.core.enterprise_reporter",
    "folder_manager": "src.services.core.folder_manager",
    "gcalendar": "src.services.core.gcalendar",
    "gcontacts": "src.services.core.gcontacts",
    "gdrive": "src.services.core.gdrive",
    "google_service": "src.services.debug.google_service",
    "gsheets": "src.services.core.gsheets",
    "juma_notifier": "src.services.core.juma_notifier",
    "lead_orchestrator": "src.services.core.lead_orchestrator",
    "lead_scraper": "src.services.core.lead_scraper",
    "mission_control": "src.services.core.mission_control",
    "monitor_resources": "src.services.core.monitor_resources",
    "proactive_worker": "src.services.core.proactive_worker",
    "safe_responder": "src.services.core.safe_responder",
    "sales_analytics": "src.services.core.sales_analytics",
    "scouter": "src.services.utils.scouter",
    "session_manager": "src.services.core.session_manager",
    "team_hub": "src.services.utils.team_hub",
    "userbot_legacy": "src.services.debug.userbot_legacy",
    "voice_processor": "src.services.utils.voice_processor",
    "welcome_manager": "src.services.utils.welcome_manager",
    "workflow_manager": "src.services.core.workflow_manager",
    "workflow_orchestrator": "src.services.core.workflow_orchestrator",
}


class _AliasModule(types.ModuleType):
    def __init__(self, module_key: str, target_path: str):
        super().__init__(module_key)
        self._module_key = module_key
        self._target_path = target_path
        self._loaded_module = None

    def _load(self):
        if self._loaded_module is None:
            self._loaded_module = import_module(self._target_path)
            sys.modules[self._module_key] = self._loaded_module
        return self._loaded_module

    def __getattr__(self, item):
        return getattr(self._load(), item)


for legacy_name, target_path in _ALIASES.items():
    module_key = f"{__name__}.{legacy_name}"
    if module_key not in sys.modules:
        sys.modules[module_key] = _AliasModule(module_key, target_path)
