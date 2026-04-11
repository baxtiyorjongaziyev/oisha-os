"""
Oisha-OS Test Configuration.

pytest-asyncio auto mode: barcha async testlar avtomatik ishlaydi.

Eski testlar `from database import Database` kabi ildiz importlarni ishlatadi.
Bu conftest.py `src/` papkasini sys.path ga qo'shib, ularni ishlashini ta'minlaydi.

Shuningdek, .env yo'q bo'lsa ham testlar crash bo'lmasligi uchun
minimal mock environment yaratadi.
"""
import os
import sys

# src/ va uning ichki papkalarini sys.path ga qo'shish (eski importlar uchun)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, "src")
services_path = os.path.join(src_path, "services")
controllers_path = os.path.join(src_path, "controllers")
agents_path = os.path.join(src_path, "agents")

for p in [project_root, src_path, services_path, controllers_path, agents_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

# .env mavjud bo'lmasa, minimal muhit o'zgaruvchilarini sozlash
# Bu testlar collection paytida crash bo'lishining oldini oladi
_required_env_vars = {
    "BOT_TOKEN": "test:fake_bot_token",
    "API_ID": "12345",
    "API_HASH": "fake_api_hash_for_testing",
    "GEMINI_API_KEY": "fake_gemini_key_for_testing",
    "AMOCRM_SUBDOMAIN": "test",
    "AMOCRM_CLIENT_ID": "fake_client_id",
}

for key, default in _required_env_vars.items():
    if key not in os.environ:
        os.environ[key] = default
