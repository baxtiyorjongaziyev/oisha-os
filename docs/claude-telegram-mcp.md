# Claude Desktop Telegram MCP troubleshooting

This note documents the working Claude Desktop configuration for the Oisha Telegram MCP bridge when Claude runs on a Windows workstation and the MCP server runs remotely on the Oracle VM over SSH.

## Recommended Claude config

Use `ssh -T` so OpenSSH does not allocate a pseudo-terminal. MCP uses stdio, so stdout must stay clean JSON-RPC output from the remote Python server.

```json
{
  "mcpServers": {
    "telegram": {
      "command": "ssh",
      "args": [
        "-T",
        "-i",
        "C:\\Users\\baxti\\.ssh\\oracle_free_tier_ed25519",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        "ubuntu@163.192.10.104",
        "cd /home/ubuntu/oisha-os && exec /home/ubuntu/oisha-os/venv/bin/python3 /home/ubuntu/oisha-os/scripts/run_telegram_mcp_agent.py --agent claude"
      ]
    }
  }
}
```

Keep the remote command as a single argument so the remote shell can run `cd ... && exec ...` in the repository directory.

## PowerShell handshake test

Run this before debugging Claude itself:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"diag","version":"1.0"}}}' | ssh -T -i C:\Users\baxti\.ssh\oracle_free_tier_ed25519 -o StrictHostKeyChecking=no -o BatchMode=yes ubuntu@163.192.10.104 "cd /home/ubuntu/oisha-os && /home/ubuntu/oisha-os/venv/bin/python3 /home/ubuntu/oisha-os/scripts/run_telegram_mcp_agent.py --agent claude"
```

Expected result: stdout contains a JSON-RPC `result` response. If the command prints a traceback or SSH error instead, fix that error before reopening Claude Desktop.

## Oracle VM checks

```bash
systemctl is-active oisha-os
curl -s -i http://127.0.0.1:8080/readyz/
cd /home/ubuntu/oisha-os
/home/ubuntu/oisha-os/venv/bin/python3 -c "import mcp; print(mcp.__file__)"
```

The bridge connects only to Oisha's loopback Telegram MCP upstream. It never
receives `USERBOT_SESSION_STRING` or `TELEGRAM_MCP_SESSION_STRING`. Read tools
run automatically; mutations are queued for owner approval through
`@jonairobot`.

## Common failure clues

- `spawn ENOENT`: Claude cannot find `ssh` or the configured command.
- `Permission denied`: SSH key path or permissions are wrong.
- `Host key verification failed`: host key is not trusted by the Windows user running Claude.
- `ModuleNotFoundError`: the Oracle VM virtualenv is missing a dependency.
- `401 Unauthorized`: `OISHA_API_SECRET` mismatch or missing environment.
- `503 Telegram client not initialized`: Oisha API is running, but the Telegram client is not active in that runtime.
- `AuthKeyDuplicatedError`: do not start a second Telegram userbot session; Oracle VM is the session owner.
