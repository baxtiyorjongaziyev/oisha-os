const fs = require('fs');
const path = 'C:\\Users\\baxti\\AppData\\Roaming\\Claude\\claude_desktop_config.json';
const data = fs.readFileSync(path, 'utf8');
const config = JSON.parse(data);

config.mcpServers.oisha.command = "C:\\WINDOWS\\System32\\OpenSSH\\ssh.exe";
config.mcpServers.oisha.args = [
  "-T",
  "-i",
  "C:/Users/baxti/.ssh/oracle_free_tier_ed25519",
  "-o",
  "StrictHostKeyChecking=no",
  "-o",
  "BatchMode=yes",
  "-o",
  "ConnectTimeout=15",
  "-o",
  "ServerAliveInterval=15",
  "-o",
  "ServerAliveCountMax=6",
  "-o",
  "TCPKeepAlive=yes",
  "ubuntu@163.192.10.104",
  "/home/ubuntu/oisha-os/venv/bin/python3",
  "-u",
  "/home/ubuntu/oisha-os/scripts/oisha_mcp_server.py"
];
delete config.mcpServers.oisha.env;

fs.writeFileSync(path, JSON.stringify(config, null, 2));
console.log("Config updated.");
