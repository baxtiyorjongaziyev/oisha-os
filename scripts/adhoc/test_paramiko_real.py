import paramiko
import sys
host = "163.192.10.104"
username = "ubuntu"
key_filename = r"C:\Users\baxti\.ssh\oracle_free_tier_ed25519"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=username, key_filename=key_filename)
stdin, stdout, stderr = client.exec_command("/opt/oisha-os/.venv/bin/python3 -u /opt/oisha-os/scripts/telegram_mcp_server.py")
import json
init_msg = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}
stdin.write(json.dumps(init_msg) + "\n")
stdin.flush()
print(stdout.readline())
