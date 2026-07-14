import subprocess
import json
import time
import threading

cmd = [
    "ssh", "-i", "C:/Users/baxti/.ssh/oracle_free_tier_ed25519",
    "-o", "StrictHostKeyChecking=no",
    "ubuntu@163.192.10.104",
    "/opt/oisha-os/.venv/bin/python3",
    "/opt/oisha-os/scripts/telegram_mcp_server.py"
]

p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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

def read_stdout():
    for line in p.stdout:
        print(f"Stdout: {line.strip()}")

def read_stderr():
    for line in p.stderr:
        print(f"Stderr: {line.strip()}")

t1 = threading.Thread(target=read_stdout, daemon=True)
t1.start()
t2 = threading.Thread(target=read_stderr, daemon=True)
t2.start()

p.stdin.write(json.dumps(init_msg) + "\n")
p.stdin.flush()

time.sleep(2)
if p.poll() is not None:
    print(f"Process exited with code {p.returncode}")
else:
    print("Process still running. Killing it.")
    p.kill()
