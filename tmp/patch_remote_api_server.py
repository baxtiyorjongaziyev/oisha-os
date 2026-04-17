from pathlib import Path

path = Path('/home/baxti/oisha-os/src/api_server.py')
text = path.read_text(encoding='utf-8')

if 'def set_runtime_context' in text:
    print('already_patched')
    raise SystemExit(0)

old_root = '''@app.get("/")
async def root_status():
    """Health check for Google Cloud Run."""
    return {
        "status": "online",
        "service": "Oisha-OS Enterprise",
        "version": "2.1.0-GodMode",
        "timestamp": datetime.now().isoformat()
    }
'''

new_root = '''@app.get("/")
async def root_status():
    """Health check for Google Cloud Run."""
    response = {
        "status": "online",
        "service": "Oisha-OS Enterprise",
        "version": "2.1.0-GodMode",
        "timestamp": datetime.now().isoformat(),
        "runtime": get_runtime_context(),
    }
    response.update(cached_status)
    return response
'''

anchor = '''# Global references
user_client = None
db_instance = None
outgoing_messages: asyncio.Queue = None  # Initialized lazily; bridge consumer checks before use
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = []
'''

insert = '''# Global references
user_client = None
db_instance = None
outgoing_messages: asyncio.Queue = None  # Initialized lazily; bridge consumer checks before use
cached_status: Dict[str, Any] = {
    "status": "offline",
    "message": "Tizim tayyorlanmoqda...",
    "timestamp": datetime.now().isoformat(),
}
runtime_context: Dict[str, Any] = {
    "service_name": "oisha-main",
    "runtime_source": "vm",
    "runtime_id": "legacy-vm",
    "state_backend": "sqlite",
    "state_db_path": None,
    "userbot_authorized": None,
}
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = []


def get_runtime_context() -> Dict[str, Any]:
    return dict(runtime_context)


def set_runtime_context(**kwargs) -> Dict[str, Any]:
    runtime_context.update({key: value for key, value in kwargs.items() if value is not None})
    if db_instance and not runtime_context.get("state_db_path"):
        runtime_context["state_db_path"] = getattr(db_instance, "db_path", None)
    return get_runtime_context()


def update_api_status(status: str, message: str) -> Dict[str, Any]:
    global cached_status
    cached_status = {
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    return dict(cached_status)
'''

if old_root not in text:
    raise SystemExit('root_status anchor not found')
if anchor not in text:
    raise SystemExit('global anchor not found')

text = text.replace(old_root, new_root, 1)
text = text.replace(anchor, insert, 1)
path.write_text(text, encoding='utf-8')
print('patched')
