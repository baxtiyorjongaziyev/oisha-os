import re
import sys

path = "/home/ubuntu/oisha-os/src/api_server.py"
with open(path, "r") as f:
    content = f.read()

new_content = re.sub(
    r'app\.mount\("/telegram-mcp", telegram_mcp_instance\.sse_app\(mount_path="/telegram-mcp"\)\)',
    'mcp_path = f"/telegram-mcp-{os.environ.get(\'OISHA_API_SECRET\', \'default\')}"\n    app.mount(mcp_path, telegram_mcp_instance.sse_app(mount_path=mcp_path))',
    content
)

new_content = re.sub(
    r'logger\.info\("\[MCP\] Telegram SSE MCP server mounted at /telegram-mcp"\)',
    'logger.info(f"[MCP] Telegram SSE MCP server mounted at {mcp_path}")',
    new_content
)

with open(path, "w") as f:
    f.write(new_content)
print("api_server.py patched")
