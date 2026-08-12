import re

path = "/home/ubuntu/oisha-os/src/api_server.py"
with open(path, "r") as f:
    content = f.read()

# Change the import to import from oisha_mcp_server
new_content = re.sub(
    r'from telegram_mcp_server import mcp as telegram_mcp_instance',
    'from oisha_mcp_server import mcp as telegram_mcp_instance',
    content
)

with open(path, "w") as f:
    f.write(new_content)
print("api_server.py import patched")
